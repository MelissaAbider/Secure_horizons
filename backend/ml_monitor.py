"""R6_ML_ANOMALY: local, read-only statistical corroborator over live Snapshot windows.

This is the production adapter for the selected model family (robust covariance / Elliptic Envelope). The historical v2
model in evaluation/ uses decoded Aave event-flow features and cannot consume Snapshot objects. This adapter therefore
uses only state features present in the live collector contract: bridge gaps, collateral changes, liquidity changes,
utilisation/APY, exact treasury exitability and containment flags.

The estimator is fitted from a configured baseline file of NORMAL snapshots, never from the live stream. That prevents an
attack from poisoning its own baseline. Its score threshold is a configured normal-score quantile. Until enough valid
baseline samples exist, R6 reports unavailable and emits no alert. R6 is capped at high; consensus downgrades it to warning
when no other surveillance layer agrees.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from backend import rules, settings
from backend.models import Alert, Snapshot

RULE_ID = "R6_ML_ANOMALY"
MODEL_CONFIG_PATH = settings.CONFIG_DIR / "ml_monitor.json"


@dataclass
class MLStatus:
    enabled: bool = True
    available: bool = False
    last_error: str | None = None
    baseline_samples: int = 0
    score: float | None = None
    threshold: float | None = None
    model_hash: str = ""


def _ratio(n: int, d: int) -> float:
    return n / d if d else (1.0 if n else 0.0)


def snapshot_features(window: list[Snapshot]) -> tuple[list[float], dict[str, float]]:
    """Chain/token-scale-independent state and delta features available identically in fixture and live collection."""
    current = window[-1]
    prior = window[0] if len(window) > 1 else current
    token_now = {t.symbol: t for t in current.tokens}
    token_before = {t.symbol: t for t in prior.tokens}
    reserve_now = {(r.deployment_id, r.asset): r for r in current.reserves}
    reserve_before = {(r.deployment_id, r.asset): r for r in prior.reserves}
    position_now = {(p.deployment_id, p.asset): p for p in current.positions}

    rs = token_now.get("rsETH")
    rs0 = token_before.get("rsETH")
    released_gap = nonce_gap = bridge_paused = 0.0
    if rs:
        if rs.bridge_source_locked is not None and rs.bridge_destination_released is not None:
            released_gap = max(0.0, _ratio(int(rs.bridge_destination_released) - int(rs.bridge_source_locked), max(1, int(rs.bridge_source_locked))))
        if rs.bridge_source_nonce is not None and rs.bridge_destination_nonce is not None:
            nonce_gap = float(max(0, rs.bridge_destination_nonce - rs.bridge_source_nonce))
        bridge_paused = float(bool(rs.bridge_paused))

    collateral_growth = liquidity_drop = utilization = apy_growth = frozen = paused = 0.0
    exitability_loss = 0.0
    for key, r in reserve_now.items():
        old = reserve_before.get(key, r)
        if r.asset == "rsETH":
            collateral_growth = max(collateral_growth, max(0.0, _ratio(int(r.total_collateral) - int(old.total_collateral), max(1, int(old.total_collateral)))))
        if r.asset in ("WETH", "USDC"):
            liquidity_drop = max(liquidity_drop, max(0.0, _ratio(int(old.available_liquidity) - int(r.available_liquidity), max(1, int(old.available_liquidity)))))
            utilization = max(utilization, r.utilization_bps / 10_000)
            apy_growth = max(apy_growth, max(0.0, (r.borrow_apy_bps - old.borrow_apy_bps) / 10_000))
        frozen = max(frozen, float(r.frozen))
        paused = max(paused, float(r.paused))
    for p in position_now.values():
        supplied = int(p.supplied)
        exitability_loss = max(exitability_loss, 1.0 - _ratio(int(p.withdrawable_now), supplied) if supplied else 0.0)

    named = {"released_gap": released_gap, "nonce_gap": nonce_gap, "bridge_paused": bridge_paused,
             "collateral_growth": collateral_growth, "liquidity_drop": liquidity_drop, "utilization": utilization,
             "apy_growth": apy_growth, "exitability_loss": exitability_loss, "reserve_frozen": frozen, "reserve_paused": paused,
             "bridge_x_collateral": released_gap * collateral_growth,
             "collateral_x_drain": collateral_growth * liquidity_drop,
             "drain_x_exitability": liquidity_drop * exitability_loss}
    return list(named.values()), named


class MLMonitor:
    def __init__(self, cfg: dict | None = None, baseline_path: Path | None = None, allow_non_live: bool = False):
        self.cfg = cfg or json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
        self.allow_non_live = allow_non_live
        self.baseline_path = baseline_path or (settings.ROOT / self.cfg["baseline_file"])
        self.status = MLStatus(enabled=bool(self.cfg.get("enabled", True)))
        self._model = None

    def _fit(self) -> None:
        if not self.status.enabled:
            self.status.last_error = "disabled"
            return
        try:
            import numpy as np
            from sklearn.covariance import EllipticEnvelope
            snapshots = [Snapshot.model_validate_json(line) for line in self.baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            span = int(self.cfg["window_snapshots"])
            samples = [snapshot_features(snapshots[max(0, i - span + 1):i + 1])[0] for i in range(len(snapshots))]
            if len(samples) < int(self.cfg["min_baseline_samples"]):
                raise ValueError("insufficient baseline")
            self._model = EllipticEnvelope(contamination=float(self.cfg["contamination"]), support_fraction=float(self.cfg["support_fraction"]), random_state=42).fit(samples)
            scores = -self._model.score_samples(samples)
            self.status.baseline_samples = len(samples)
            self.status.threshold = float(np.quantile(scores, float(self.cfg["score_quantile"])))
            config_bytes = MODEL_CONFIG_PATH.read_bytes() if MODEL_CONFIG_PATH.exists() else json.dumps(self.cfg, sort_keys=True).encode()
            self.status.model_hash = "sha256:" + hashlib.sha256(config_bytes + self.baseline_path.read_bytes()).hexdigest()
            self.status.available = True
        except Exception as exc:
            self.status.available = False
            self.status.last_error = type(exc).__name__

    def evaluate(self, window: list[Snapshot]) -> tuple[list[Alert], list[str]]:
        if not self.status.enabled:
            return [], ["R6 ML disabled"]
        if not window:
            return [], ["R6 ML: no snapshot"]
        if not self.allow_non_live and (window[-1].source != "live" or not settings.ENGINE_ENABLED):
            return [], ["R6 ML live adapter inactive (requires live input and ENGINE_ENABLED=true)"]
        if self._model is None and self.status.last_error is None:
            self._fit()
        if not self.status.available or self._model is None or self.status.threshold is None:
            return [], [f"R6 ML unavailable ({self.status.last_error or 'not fitted'})"]
        vector, named = snapshot_features(window[-int(self.cfg["window_snapshots"]):])
        score = float(-self._model.score_samples([vector])[0])
        self.status.score = score
        if score <= self.status.threshold:
            return [], []
        s = window[-1]
        relevant = sorted(named.items(), key=lambda item: item[1], reverse=True)[:4]
        phases = []
        if named["released_gap"] or named["nonce_gap"]:
            phases.append("bridge")
        if named["collateral_growth"]:
            phases.append("collateral")
        if named["liquidity_drop"] or named["utilization"] >= 0.9:
            phases.append("liquidity")
        if named["exitability_loss"]:
            phases.append("exitability")
        if named["bridge_paused"] or named["reserve_frozen"] or named["reserve_paused"]:
            phases.append("containment")
        exposure = sum(p.value_usd for p in s.positions)
        explanation = "Robust-covariance anomaly on live state: " + ", ".join(f"{k}={v:.4g}" for k, v in relevant)
        alert = Alert(id=f"ALT-{s.network}-{s.block_number}-{RULE_ID}-global-all", rule_id=RULE_ID, severity="high",
                      network=s.network, deployment_id=None, asset=None, block_number=s.block_number, block_time=s.block_time,
                      detected_at=s.block_time, title="ML: anomalous KelpDAO state sequence", explanation=explanation,
                      metrics={"layer": "ml", "score": round(score, 6), "threshold": round(self.status.threshold, 6), "phases": phases},
                      exposure_usd=round(exposure, 2), rules_version=f"{rules.rules_version()}+ml:{self.status.model_hash[7:19]}")
        return [alert], []
