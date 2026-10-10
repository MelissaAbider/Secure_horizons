from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from backend import settings
from backend.models import Alert, PositionSnapshot, ReserveSnapshot, Snapshot, TokenSnapshot

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
RULES_PATH = settings.CONFIG_DIR / "rules.yaml"


def rules_version(path: Path = RULES_PATH) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_rules(path: Path = RULES_PATH) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_version"] = rules_version(path)
    return cfg


def treasury_positions(s: Snapshot) -> dict[tuple[str, str], PositionSnapshot]:
    return {(p.deployment_id, p.asset): p for p in s.positions if int(p.supplied) > 0}


def position_value(s: Snapshot, deployment_id: str, asset: str) -> float:
    position = treasury_positions(s).get((deployment_id, asset))
    return position.value_usd if position else 0.0


def deployment_exposure(s: Snapshot, deployment_id: str) -> float:
    return round(sum(p.value_usd for p in s.positions if p.deployment_id == deployment_id), 2)


def collateral_exposure(s: Snapshot, token: str) -> tuple[float, list[str]]:
    deployments = sorted({r.deployment_id for r in s.reserves if r.asset == token and r.ltv_bps > 0})
    return round(sum(deployment_exposure(s, deployment_id) for deployment_id in deployments), 2), deployments


def _reserve(s: Snapshot, deployment_id: str, asset: str) -> ReserveSnapshot | None:
    return next((r for r in s.reserves if r.deployment_id == deployment_id and r.asset == asset), None)


def _token(s: Snapshot, symbol: str) -> TokenSnapshot | None:
    return next((t for t in s.tokens if t.symbol == symbol), None)


def _human(value: str | int, decimals: int) -> float:
    return int(value) / 10**decimals


def _fmt(value: float) -> str:
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _alert(s: Snapshot, cfg: dict, rule_id: str, severity: str, deployment_id: str | None, asset: str | None,
           title: str, explanation: str, metrics: dict, exposure: float) -> Alert:
    scope = deployment_id or "global"
    return Alert(id=f"ALT-{s.network}-{s.block_number}-{rule_id}-{scope}-{asset or 'all'}", rule_id=rule_id,
                 severity=severity, network=s.network, deployment_id=deployment_id, asset=asset,
                 block_number=s.block_number, block_time=s.block_time, detected_at=s.block_time,
                 title=title, explanation=explanation, metrics=metrics, exposure_usd=round(exposure, 2),
                 rules_version=cfg["_version"])


def evaluate_r1(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg["R1_BRIDGE_INVARIANT"]
    if not window or not rule["enabled"]:
        return []
    s = window[-1]
    alerts = []
    for token in s.tokens:
        fields = (token.bridge_source_locked, token.bridge_destination_released,
                  token.bridge_source_nonce, token.bridge_destination_nonce)
        if any(value is None for value in fields):
            continue
        source = int(token.bridge_source_locked)
        released = int(token.bridge_destination_released)
        gap = max(released - source, 0)
        if gap == 0 and token.bridge_destination_nonce <= token.bridge_source_nonce:
            continue
        exposure, deployments = collateral_exposure(s, token.symbol)
        gap_human = _human(gap, token.decimals)
        source_human = _human(source, token.decimals)
        released_human = _human(released, token.decimals)
        explanation = (f"The {token.symbol} bridge released {_fmt(gap_human)} tokens without canonical source backing; "
                       f"destination nonce {token.bridge_destination_nonce} is ahead of source nonce {token.bridge_source_nonce}.")
        alerts.append(_alert(s, cfg, "R1_BRIDGE_INVARIANT", "critical", None, token.symbol,
                             f"{token.symbol} bridge invariant broken", explanation,
                             {"source_locked": source_human, "destination_released": released_human,
                              "conservation_gap": gap_human, "source_nonce": token.bridge_source_nonce,
                              "destination_nonce": token.bridge_destination_nonce,
                              "exposed_deployments": ",".join(deployments)}, exposure))
    return alerts


def evaluate_r2(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg["R2_COLLATERAL_SURGE"]
    if len(window) < 3 or not rule["enabled"]:
        return []
    s, asset = window[-1], rule["asset"]
    alerts = []
    for current in (r for r in s.reserves if r.asset == asset and r.ltv_bps > 0):
        history = [int(r.total_collateral) for old in window[:-1]
                   if (r := _reserve(old, current.deployment_id, asset)) is not None]
        baseline = max(history) if len(history) >= 2 else 0
        now = int(current.total_collateral)
        if baseline <= 0 or now <= baseline:
            continue
        increase_bps = (now - baseline) * 10_000 // baseline
        severity = "critical" if increase_bps >= rule["critical_increase_pct"] * 100 else "high" if increase_bps >= rule["high_increase_pct"] * 100 else None
        if severity is None:
            continue
        baseline_h, now_h = _human(baseline, current.decimals), _human(now, current.decimals)
        pct = increase_bps / 100
        alerts.append(_alert(s, cfg, "R2_COLLATERAL_SURGE", severity, current.deployment_id, asset,
                             f"{asset} collateral surge on {current.deployment_id}",
                             f"{asset} collateral on {current.deployment_id} rose {pct:.1f} % within the last {len(window)} snapshots (from {_fmt(baseline_h)} to {_fmt(now_h)} {asset}).",
                             {"total_collateral": now_h, "baseline_collateral": baseline_h,
                              "increase_pct": pct, "window_snapshots": len(window)},
                             deployment_exposure(s, current.deployment_id)))
    return alerts


def evaluate_r3(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg["R3_LIQUIDITY_DRAIN"]
    if len(window) < 2 or not rule["enabled"]:
        return []
    s, alerts, positions = window[-1], [], treasury_positions(window[-1])
    for current in (r for r in s.reserves if r.borrowable and (r.deployment_id, r.asset) in positions):
        history = [int(r.available_liquidity) for old in window[:-1]
                   if (r := _reserve(old, current.deployment_id, current.asset)) is not None]
        baseline = max(history) if history else 0
        now = int(current.available_liquidity)
        if baseline <= 0:
            continue
        drop_bps = (baseline - now) * 10_000 // baseline
        severity = "critical" if drop_bps >= rule["critical_drop_pct"] * 100 else "high" if drop_bps >= rule["high_drop_pct"] * 100 else None
        if severity is None:
            continue
        max_h, now_h, pct = _human(baseline, current.decimals), _human(now, current.decimals), drop_bps / 100
        alerts.append(_alert(s, cfg, "R3_LIQUIDITY_DRAIN", severity, current.deployment_id, current.asset,
                             f"{current.asset} liquidity draining on {current.deployment_id}",
                             f"Available {current.asset} liquidity on {current.deployment_id} fell {pct:.1f} % within the last {len(window)} snapshots (from {_fmt(max_h)} to {_fmt(now_h)} {current.asset}).",
                             {"available_liquidity": now_h, "max_available_liquidity": max_h,
                              "drop_pct": pct, "window_snapshots": len(window)},
                             position_value(s, current.deployment_id, current.asset)))
    return alerts


def evaluate_r4(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg["R4_EXITABILITY_DROP"]
    if not window or not rule["enabled"]:
        return []
    s, alerts = window[-1], []
    for position in s.positions:
        if int(position.supplied) <= 0:
            continue
        ratio = position.withdrawable_ratio_bps
        severity = "critical" if ratio < rule["critical_below_bps"] else "high" if ratio < rule["high_below_bps"] else None
        if severity is None:
            continue
        reserve = _reserve(s, position.deployment_id, position.asset)
        decimals = reserve.decimals if reserve else 18
        supplied, withdrawable = _human(position.supplied, decimals), _human(position.withdrawable_now, decimals)
        alerts.append(_alert(s, cfg, "R4_EXITABILITY_DROP", severity, position.deployment_id, position.asset,
                             f"Our {position.asset} exitability dropped on {position.deployment_id}",
                             f"Only {ratio / 100:.1f} % of our {_fmt(supplied)} {position.asset} position on {position.deployment_id} can be withdrawn now ({_fmt(withdrawable)} {position.asset}).",
                             {"withdrawable_ratio_bps": ratio, "withdrawable_now": withdrawable,
                              "supplied": supplied, "threshold_bps": rule[f"{severity}_below_bps"]},
                             position.value_usd))
    return alerts


def evaluate_r5(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg["R5_CONTAINMENT"]
    if len(window) < 2 or not rule["enabled"]:
        return []
    prev, s, alerts = window[-2], window[-1], []
    for current in s.reserves:
        if deployment_exposure(s, current.deployment_id) <= 0:
            continue
        before = _reserve(prev, current.deployment_id, current.asset)
        if before is None or not (current.frozen or current.paused) or before.frozen or before.paused:
            continue
        positions = [p for p in s.positions if p.deployment_id == current.deployment_id]
        min_ratio = min((p.withdrawable_ratio_bps for p in positions), default=10_000)
        severity = "critical" if min_ratio < rule["critical_withdrawable_below_bps"] else "high"
        state = "frozen+paused" if current.frozen and current.paused else "frozen" if current.frozen else "paused"
        alerts.append(_alert(s, cfg, "R5_CONTAINMENT", severity, current.deployment_id, current.asset,
                             f"{current.asset} containment activated on {current.deployment_id}",
                             f"The {current.asset} reserve on {current.deployment_id} was {state}; only {min_ratio / 100:.1f} % of the least liquid treasury position is withdrawable.",
                             {"state": state, "scope": "reserve", "withdrawable_ratio_bps": min_ratio},
                             deployment_exposure(s, current.deployment_id)))
    return alerts


def evaluate_all(window: list[Snapshot], cfg: dict) -> list[Alert]:
    if not window:
        return []
    candidates = evaluate_r1(window, cfg) + evaluate_r2(window, cfg) + evaluate_r3(window, cfg) + evaluate_r4(window, cfg) + evaluate_r5(window, cfg)
    return sorted(candidates, key=lambda a: (a.rule_id, a.deployment_id or "", a.asset or ""))


class AlertLatch:
    def __init__(self) -> None:
        self._active: dict[tuple[str, str | None, str | None], str] = {}

    def filter(self, candidates: list[Alert]) -> list[Alert]:
        current = {(a.rule_id, a.deployment_id, a.asset): a for a in candidates}
        for key in set(self._active) - set(current):
            del self._active[key]
        emitted = []
        for key, alert in current.items():
            previous = self._active.get(key)
            if previous is None or SEVERITY_RANK[alert.severity] > SEVERITY_RANK[previous]:
                emitted.append(alert)
                self._active[key] = alert.severity
        return emitted

    def active(self) -> dict[tuple[str, str | None, str | None], str]:
        return dict(self._active)

    def reset(self) -> None:
        self._active.clear()
