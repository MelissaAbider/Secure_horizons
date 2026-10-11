from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from backend import settings
from backend.models import Alert, PositionSnapshot, ReserveSnapshot, Snapshot, TokenSnapshot

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
RULES_PATH = settings.CONFIG_DIR / "rules.yaml"
RULE_IDS = ("R1_BRIDGE_INVARIANT", "R2_COLLATERAL_SURGE", "R3_LIQUIDITY_DRAIN", "R4_EXITABILITY_DROP", "R5_CONTAINMENT")


@dataclass
class Evaluation:
    alerts: list[Alert] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    unavailable_rules: set[str] = field(default_factory=set)


def rules_version(path: Path = RULES_PATH) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(cfg: dict) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("Rules configuration must be a mapping")
    for key, minimum in (("version", 1), ("window_snapshots", 3), ("max_snapshot_age_s", 1),
                         ("max_future_skew_s", 0), ("handler_queue_size", 1)):
        if type(cfg.get(key)) is not int or cfg[key] < minimum:
            raise ValueError(f"Invalid configuration: {key}")
    if not isinstance(cfg.get("_version"), str) or not cfg["_version"].startswith("sha256:"):
        raise ValueError("Missing rules content hash")
    for name in RULE_IDS:
        if not isinstance(cfg.get(name), dict) or type(cfg[name].get("enabled")) is not bool:
            raise ValueError(f"Invalid enabled flag: {name}")
    if not isinstance(cfg[RULE_IDS[1]].get("asset"), str) or not cfg[RULE_IDS[1]]["asset"]:
        raise ValueError("Missing collateral asset")
    for name, low, high, maximum in (
        (RULE_IDS[1], "high_increase_pct", "critical_increase_pct", None),
        (RULE_IDS[2], "high_drop_pct", "critical_drop_pct", 100),
        (RULE_IDS[2], "bridge_anomaly_drop_pct", "high_drop_pct", 100),
        (RULE_IDS[2], "warning_utilization_bps", "critical_utilization_bps", 10_000),
        (RULE_IDS[3], "critical_below_bps", "high_below_bps", 10_000),
    ):
        a, b = cfg[name].get(low), cfg[name].get(high)
        if type(a) is not int or type(b) is not int or not 0 < a < b or (maximum is not None and b > maximum):
            raise ValueError(f"Invalid or inverted thresholds: {name}")
    cutoff = cfg[RULE_IDS[4]].get("critical_withdrawable_below_bps")
    if type(cutoff) is not int or not 0 < cutoff <= 10_000:
        raise ValueError("Invalid containment threshold")


def load_rules(path: Path = RULES_PATH) -> dict:
    raw = path.read_bytes()
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict):
        raise ValueError("Rules configuration must be a mapping")
    cfg["_version"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    validate_config(cfg)
    return cfg


def _amount(value: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("Amounts must be nonnegative base-unit integer strings")
    amount = int(value)
    if amount >= 2**256:
        raise ValueError("Amount exceeds uint256")
    return amount


def _unique(values: list, name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate {name}")


def validate_snapshot(s: Snapshot) -> None:
    if s.block_number < 0 or s.chain_id <= 0 or s.block_time.utcoffset() is None:
        raise ValueError("Invalid block identity or timestamp")
    if not s.tokens or not s.reserves:
        raise ValueError("Snapshot inventory is empty")
    _unique([(r.deployment_id, r.asset) for r in s.reserves], "reserve")
    _unique([t.symbol for t in s.tokens], "token")
    _unique([(p.deployment_id, p.asset) for p in s.positions], "position")
    tokens = {t.symbol: t for t in s.tokens}
    reserves = {(r.deployment_id, r.asset): r for r in s.reserves}
    for item in [*s.tokens, *s.reserves]:
        if not 0 <= item.decimals <= 77 or not math.isfinite(item.price_usd) or item.price_usd < 0:
            raise ValueError("Invalid decimals or price")
    for t in s.tokens:
        for value in (t.total_supply, t.backing, t.bridge_source_locked, t.bridge_destination_released):
            if value is not None:
                _amount(value)
        for nonce in (t.bridge_source_nonce, t.bridge_destination_nonce):
            if nonce is not None and (type(nonce) is not int or not 0 <= nonce < 2**64):
                raise ValueError("Invalid bridge nonce")
    for r in s.reserves:
        t = tokens.get(r.asset)
        if t is None or t.address.lower() != r.asset_address.lower() or t.decimals != r.decimals:
            raise ValueError("Reserve token metadata is missing or inconsistent")
        for value in (r.total_supplied, r.total_borrowed, r.total_collateral, r.available_liquidity):
            _amount(value)
        if not 0 <= r.utilization_bps <= 10_000 or not 0 <= r.ltv_bps <= 10_000:
            raise ValueError("Invalid reserve ratio")
    for p in s.positions:
        if (p.deployment_id, p.asset) not in reserves or p.wallet.lower() != s.vault.address.lower():
            raise ValueError("Position reserve is missing or wallet is not the treasury")
        _amount(p.supplied)
        _amount(p.withdrawable_now)
        if not 0 <= p.withdrawable_ratio_bps <= 10_000:
            raise ValueError("Invalid position ratio")
        if any(not math.isfinite(v) or v < 0 for v in (p.value_usd, p.withdrawable_usd)):
            raise ValueError("Invalid position valuation")
    for value in s.vault.idle_balances.values():
        _amount(value)


def treasury_positions(s: Snapshot) -> dict[tuple[str, str], PositionSnapshot]:
    return {(p.deployment_id, p.asset): p for p in s.positions if int(p.supplied) > 0}


def position_value(s: Snapshot, deployment_id: str, asset: str) -> float:
    p = treasury_positions(s).get((deployment_id, asset))
    return p.value_usd if p else 0.0


def deployment_exposure(s: Snapshot, deployment_id: str) -> float:
    return round(sum(p.value_usd for p in treasury_positions(s).values() if p.deployment_id == deployment_id), 2)


def _collateral_deployments(s: Snapshot, token: str) -> list[str]:
    exposed = {p.deployment_id for p in treasury_positions(s).values()}
    return sorted({r.deployment_id for r in s.reserves if r.asset == token and r.deployment_id in exposed
                   and (r.ltv_bps > 0 or int(r.total_collateral) > 0)})


def collateral_exposure(s: Snapshot, token: str) -> tuple[float, list[str]]:
    deployments = _collateral_deployments(s, token)
    return round(sum(deployment_exposure(s, d) for d in deployments), 2), deployments


def _reserve(s: Snapshot, deployment_id: str, asset: str) -> ReserveSnapshot | None:
    return next((r for r in s.reserves if (r.deployment_id, r.asset) == (deployment_id, asset)), None)


def _token(s: Snapshot, symbol: str) -> TokenSnapshot | None:
    return next((t for t in s.tokens if t.symbol == symbol), None)


def _human(value: str | int, decimals: int) -> float:
    return int(value) / 10**decimals


def _fmt(value: float) -> str:
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _alert(s: Snapshot, cfg: dict, rule_id: str, severity: str, deployment_id: str | None, asset: str | None,
           title: str, explanation: str, metrics: dict, exposure: float) -> Alert:
    return Alert(id=f"ALT-{s.network}-{s.block_number}-{rule_id}-{deployment_id or 'global'}-{asset or 'all'}",
                 rule_id=rule_id, severity=severity, network=s.network, deployment_id=deployment_id, asset=asset,
                 block_number=s.block_number, block_time=s.block_time, detected_at=s.block_time,
                 title=title, explanation=explanation, metrics=metrics, exposure_usd=round(exposure, 2),
                 rules_version=cfg["_version"])


def _bridge_complete(t: TokenSnapshot) -> bool:
    return all(v is not None for v in (t.bridge_source_locked, t.bridge_destination_released,
                                       t.bridge_source_nonce, t.bridge_destination_nonce))


def _bridge_mismatch(t: TokenSnapshot) -> bool:
    return _bridge_complete(t) and (int(t.bridge_destination_released) > int(t.bridge_source_locked)
                                   or t.bridge_destination_nonce > t.bridge_source_nonce)


def _synthetic(s: Snapshot) -> bool:
    return s.source == "fixture"


def bridge_anomaly_in_window(window: list[Snapshot], asset: str) -> bool:
    return any((t := _token(s, asset)) is not None and _bridge_mismatch(t) for s in window)


def evaluate_r1(window: list[Snapshot], cfg: dict) -> list[Alert]:
    if not window or not cfg[RULE_IDS[0]]["enabled"]:
        return []
    s, result = window[-1], []
    t = _token(s, cfg[RULE_IDS[1]]["asset"])
    if t is None or not _bridge_mismatch(t):
        return result
    source, released = int(t.bridge_source_locked), int(t.bridge_destination_released)
    gap = max(released - source, 0)
    synthetic = _synthetic(s)
    facts = []
    if gap:
        facts.append(f"released counter exceeds source counter by {_fmt(_human(gap, t.decimals))} {t.symbol}")
    if t.bridge_destination_nonce > t.bridge_source_nonce:
        facts.append(f"destination nonce {t.bridge_destination_nonce} is ahead of source nonce {t.bridge_source_nonce}")
    exposure, deployments = collateral_exposure(s, t.symbol)
    severity = "critical" if deployments else "high"
    qualification = ("Synthetic bridge invariant violation." if synthetic
                     else "Counter mismatch observed on-chain; canonical source-message proof is unavailable, so this is an unverified but actionable bridge integrity failure.")
    if deployments:
        qualification += f" Treasury positions in {', '.join(deployments)} accept this collateral."
    result.append(_alert(s, cfg, RULE_IDS[0], severity, None, t.symbol,
                         f"{t.symbol} bridge counter mismatch", "; ".join(facts) + ". " + qualification,
                         {"source_locked": _human(source, t.decimals), "destination_released": _human(released, t.decimals),
                          "conservation_gap": _human(gap, t.decimals), "conservation_gap_base_units": str(gap),
                          "source_nonce": t.bridge_source_nonce, "destination_nonce": t.bridge_destination_nonce,
                          "evidence_status": "synthetic" if synthetic else "unverified",
                          "exposed_deployments": ",".join(deployments)}, exposure))
    return result


def evaluate_r2(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg[RULE_IDS[1]]
    if len(window) < 3 or not rule["enabled"]:
        return []
    s, asset, result = window[-1], rule["asset"], []
    correlated = bool(cfg[RULE_IDS[0]]["enabled"] and bridge_anomaly_in_window(window, asset))
    for deployment in _collateral_deployments(s, asset):
        r = _reserve(s, deployment, asset)
        history = [int(old.total_collateral) for snap in window[:-1]
                   if (old := _reserve(snap, deployment, asset)) is not None]
        if len(history) < 2:
            continue
        baseline, now = min(history), int(r.total_collateral)
        delta = now - baseline
        if delta <= 0 or delta * 100 < baseline * rule["high_increase_pct"]:
            continue
        severity = "warning"
        if correlated:
            severity = "critical" if baseline and delta * 100 >= baseline * rule["critical_increase_pct"] else "high"
        metrics = {"total_collateral": _human(now, r.decimals), "baseline_collateral": _human(baseline, r.decimals),
                   "baseline_base_units": str(baseline), "collateral_base_units": str(now),
                   "window_snapshots": len(window), "bridge_correlated": str(correlated).lower(),
                   "evidence_status": "bridge_correlated" if correlated else "uncorroborated"}
        if baseline:
            metrics["increase_pct"] = float(Decimal(delta) * 100 / Decimal(baseline))
        qualification = ("Collateral inflow follows a bridge integrity anomaly in the same window; this matches the forged-release-then-deposit pattern. Fund provenance is not individually traced."
                         if correlated else "Uncorroborated inflow; a legitimate deposit can produce this signal.")
        result.append(_alert(s, cfg, RULE_IDS[1], severity, deployment, asset, f"{asset} collateral increase on {deployment}",
                             f"Collateral increased from {_fmt(_human(baseline, r.decimals))} to {_fmt(_human(now, r.decimals))} {asset}. {qualification}",
                             metrics, deployment_exposure(s, deployment)))
    return result


def evaluate_r3(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg[RULE_IDS[2]]
    if not window or not rule["enabled"]:
        return []
    s, result = window[-1], []
    anomaly = cfg[RULE_IDS[0]]["enabled"] and bridge_anomaly_in_window(window, cfg[RULE_IDS[1]]["asset"])
    for p in treasury_positions(s).values():
        r = _reserve(s, p.deployment_id, p.asset)
        if r is None or not r.borrowable:
            continue
        history = [int(old.available_liquidity) for snap in window[:-1]
                   if (old := _reserve(snap, r.deployment_id, r.asset)) is not None]
        baseline = max(history, default=0)
        now, supplied, borrowed = int(r.available_liquidity), int(r.total_supplied), int(r.total_borrowed)
        rank, reasons = 0, []
        if baseline and (baseline - now) * 100 >= baseline * rule["high_drop_pct"]:
            rank = 3 if (baseline - now) * 100 >= baseline * rule["critical_drop_pct"] else 2
            reasons.append("relative liquidity drain")
        elif anomaly and baseline and (baseline - now) * 100 >= baseline * rule["bridge_anomaly_drop_pct"]:
            rank = 2
            reasons.append("liquidity drain after bridge anomaly")
        if supplied and borrowed * 10_000 >= supplied * rule["warning_utilization_bps"]:
            rank = max(rank, 3 if borrowed * 10_000 >= supplied * rule["critical_utilization_bps"] else 1)
            reasons.append("persistent utilization pressure")
        if now == 0:
            rank = 3
            reasons.append("no available liquidity")
        if not rank:
            continue
        metrics = {"available_liquidity": _human(now, r.decimals), "max_available_liquidity": _human(baseline, r.decimals),
                   "available_base_units": str(now), "utilization_bps": borrowed * 10_000 // supplied if supplied else 0,
                   "window_snapshots": len(window), "trigger": ", ".join(reasons)}
        if baseline:
            metrics["drop_pct"] = float(Decimal(baseline - now) * 100 / Decimal(baseline))
        result.append(_alert(s, cfg, RULE_IDS[2], ("info", "warning", "high", "critical")[rank], r.deployment_id, r.asset,
                             f"{r.asset} liquidity risk on {r.deployment_id}",
                             f"Available liquidity is {_fmt(_human(now, r.decimals))} {r.asset}; utilization is {metrics['utilization_bps'] / 100:.1f} %. Triggers: {metrics['trigger']}. This is liquidity risk, not proof of fraud.",
                             metrics, p.value_usd))
    return result


def effective_withdrawable(s: Snapshot, p: PositionSnapshot) -> int:
    r = _reserve(s, p.deployment_id, p.asset)
    if r is None:
        raise ValueError("Position reserve is missing")
    return 0 if r.paused else min(int(p.supplied), int(p.withdrawable_now), int(r.available_liquidity))


def evaluate_r4(window: list[Snapshot], cfg: dict) -> list[Alert]:
    rule = cfg[RULE_IDS[3]]
    if not window or not rule["enabled"]:
        return []
    s, result = window[-1], []
    for p in treasury_positions(s).values():
        supplied, withdrawable = int(p.supplied), effective_withdrawable(s, p)
        severity = "critical" if withdrawable * 10_000 < supplied * rule["critical_below_bps"] else "high" if withdrawable * 10_000 < supplied * rule["high_below_bps"] else None
        if severity is None:
            continue
        r = _reserve(s, p.deployment_id, p.asset)
        ratio = withdrawable * 10_000 // supplied
        result.append(_alert(s, cfg, RULE_IDS[3], severity, p.deployment_id, p.asset,
                             f"Our {p.asset} exitability dropped on {p.deployment_id}",
                             f"At most {_fmt(_human(withdrawable, r.decimals))} of {_fmt(_human(supplied, r.decimals))} {p.asset} is estimated withdrawable ({ratio / 100:.2f} %). Reserve paused: {str(r.paused).lower()}. Not an execution guarantee.",
                             {"withdrawable_ratio_bps": ratio, "withdrawable_now": _human(withdrawable, r.decimals),
                              "supplied": _human(supplied, r.decimals), "withdrawable_base_units": str(withdrawable),
                              "supplied_base_units": str(supplied), "threshold_bps": rule[f"{severity}_below_bps"]}, p.value_usd))
    return result


def _containment(s: Snapshot, cfg: dict, deployment: str | None, asset: str, state: str, positions: list[PositionSnapshot], scope: str) -> Alert:
    threshold = cfg[RULE_IDS[4]]["critical_withdrawable_below_bps"]
    ratios = [(effective_withdrawable(s, p), int(p.supplied)) for p in positions]
    critical = any(amount * 10_000 < total * threshold for amount, total in ratios)
    minimum = min((amount * 10_000 // total for amount, total in ratios), default=10_000)
    return _alert(s, cfg, RULE_IDS[4], "critical" if critical else "high", deployment, asset,
                  f"{asset} {scope} containment is active",
                  f"{scope.capitalize()} state: {state}; least liquid exposed position is estimated {minimum / 100:.2f} % withdrawable. A freeze alone does not establish withdrawal failure or fraud.",
                  {"state": state, "scope": scope, "withdrawable_ratio_bps": minimum}, sum(p.value_usd for p in positions))


def evaluate_r5(window: list[Snapshot], cfg: dict) -> list[Alert]:
    if not window or not cfg[RULE_IDS[4]]["enabled"]:
        return []
    s, result = window[-1], []
    positions = list(treasury_positions(s).values())
    for r in s.reserves:
        exposed = [p for p in positions if p.deployment_id == r.deployment_id]
        if exposed and (r.frozen or r.paused):
            state = "frozen+paused" if r.frozen and r.paused else "frozen" if r.frozen else "paused"
            result.append(_containment(s, cfg, r.deployment_id, r.asset, state, exposed, "reserve"))
    for t in s.tokens:
        if t.bridge_paused is True:
            deployments = _collateral_deployments(s, t.symbol)
            exposed = [p for p in positions if p.deployment_id in deployments]
            if exposed:
                result.append(_containment(s, cfg, None, t.symbol, "paused", exposed, "bridge"))
    return result


def evaluate_snapshot(window: list[Snapshot], cfg: dict) -> Evaluation:
    validate_config(cfg)
    report = Evaluation()
    if not window:
        report.issues.append("No snapshot available")
        report.unavailable_rules.update(RULE_IDS)
        return report
    window = window[-cfg["window_snapshots"]:]
    for index, s in enumerate(window):
        validate_snapshot(s)
        if index:
            prev = window[index - 1]
            if (prev.network, prev.chain_id, prev.vault.address, prev.source) != (s.network, s.chain_id, s.vault.address, s.source):
                raise ValueError("Mixed snapshot identities")
            if prev.block_number >= s.block_number or prev.block_time > s.block_time:
                raise ValueError("Snapshots must be ordered by increasing block and nondecreasing time")
            before = {(r.deployment_id, r.asset, r.asset_address.lower()) for r in prev.reserves}
            after = {(r.deployment_id, r.asset, r.asset_address.lower()) for r in s.reserves}
            if before != after or {t.symbol for t in prev.tokens} != {t.symbol for t in s.tokens}:
                raise ValueError("Snapshot inventory changed without an explicit monitor reset")
    s = window[-1]
    asset = cfg[RULE_IDS[1]]["asset"]
    t = _token(s, asset)
    if cfg[RULE_IDS[0]]["enabled"]:
        if t is None or not _bridge_complete(t):
            report.issues.append("Bridge counters incomplete; R1 cannot be evaluated")
            report.unavailable_rules.add(RULE_IDS[0])
        if not _synthetic(s):
            report.issues.append("Canonical cross-chain proof unavailable: counter mismatches are actionable but unverified against the source chain")
        if t is not None and _bridge_complete(t) and not _bridge_mismatch(t) and bridge_anomaly_in_window(window, asset):
            report.issues.append("Bridge counters returned to consistency after an observed mismatch; the earlier anomaly remains latched until signers reset the monitor")
    if cfg[RULE_IDS[4]]["enabled"] and (t is None or t.bridge_paused is None):
        report.issues.append("Bridge pause state unavailable")
        report.unavailable_rules.add(RULE_IDS[4])
    if any(t.price_usd == 0 for t in s.tokens):
        report.issues.append("Zero price: USD exposure may be understated")
    if cfg[RULE_IDS[1]]["enabled"] and len(window) < 3:
        report.issues.append("Collateral baseline warming up")
    for evaluate in (evaluate_r1, evaluate_r2, evaluate_r3, evaluate_r4, evaluate_r5):
        report.alerts.extend(evaluate(window, cfg))
    report.alerts.sort(key=lambda a: (a.rule_id, a.deployment_id or "", a.asset or ""))
    return report


def evaluate_all(window: list[Snapshot], cfg: dict) -> list[Alert]:
    return evaluate_snapshot(window, cfg).alerts


class AlertLatch:
    def __init__(self) -> None:
        self._active: dict[tuple[str, str | None, str | None], str] = {}

    STICKY_RULES = frozenset({RULE_IDS[0]})

    def filter(self, candidates: list[Alert], unavailable_rules: set[str] | None = None) -> list[Alert]:
        current = {}
        for alert in candidates:
            key = (alert.rule_id, alert.deployment_id, alert.asset)
            if key not in current or SEVERITY_RANK[alert.severity] > SEVERITY_RANK[current[key].severity]:
                current[key] = alert
        for key in set(self._active) - set(current):
            if key[0] not in (unavailable_rules or set()) and key[0] not in self.STICKY_RULES:
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
