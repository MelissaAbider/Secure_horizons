"""Consensus across the three surveillance layers (T3): rules R1-R5, ML R6, LLM agent R7.

Policy (docs/product/INVARIANTS.md 1, 7, 8; docs/product/THRESHOLDS.md):
- Deterministic rules are authoritative: their alerts pass through unchanged, including "critical".
- Non-deterministic layers (R6, R7) are capped at "high" and can never be forwarded as "critical".
- A non-deterministic alert is forwarded at its own severity only when CORROBORATED by another layer on the same
  scope (deployment/asset) at the same block window; otherwise it is downgraded to "warning" (investigation signal).
- Two non-deterministic layers agreeing without rules = "high": a variant outside the fixed thresholds that two
  independent detectors both see.
- Nothing here can raise a rule alert, change a threshold, or produce an action. Output is a list of alerts for T4.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.models import Alert

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
RULE_LAYER = "rules"
LAYER_OF_PREFIX = {"R6_": "ml", "R7_": "llm"}
NON_DETERMINISTIC_CAP = "high"


def layer_of(alert: Alert) -> str:
    for prefix, layer in LAYER_OF_PREFIX.items():
        if alert.rule_id.startswith(prefix):
            return layer
    return RULE_LAYER


def _scope(alert: Alert) -> tuple[str | None, str | None]:
    return alert.deployment_id, alert.asset


def _overlaps(a: tuple, b: tuple) -> bool:
    """Global alerts (None) corroborate any scope on the same axis."""
    return all(x is None or y is None or x == y for x, y in zip(a, b))


@dataclass
class ConsensusResult:
    forwarded: list[Alert] = field(default_factory=list)
    layers_alerting: set[str] = field(default_factory=set)
    corroborated: list[str] = field(default_factory=list)   # alert ids whose severity was kept thanks to agreement
    downgraded: list[str] = field(default_factory=list)      # alert ids downgraded to warning (single non-deterministic voice)
    agreement: str = "none"                                  # none | single | partial | full

    @property
    def max_severity(self) -> str:
        return max((a.severity for a in self.forwarded), key=lambda s: SEVERITY_RANK[s], default="info")


def _cap(alert: Alert) -> Alert:
    if SEVERITY_RANK[alert.severity] > SEVERITY_RANK[NON_DETERMINISTIC_CAP]:
        return alert.model_copy(update={"severity": NON_DETERMINISTIC_CAP})
    return alert


def resolve(alerts: list[Alert]) -> ConsensusResult:
    res = ConsensusResult()
    by_layer: dict[str, list[Alert]] = {}
    for a in alerts:
        by_layer.setdefault(layer_of(a), []).append(a)
    res.layers_alerting = {layer for layer, items in by_layer.items() if any(SEVERITY_RANK[a.severity] >= 1 for a in items)}
    res.forwarded.extend(by_layer.get(RULE_LAYER, []))
    for layer in ("ml", "llm"):
        for a in by_layer.get(layer, []):
            a = _cap(a)
            others = [o for l, items in by_layer.items() if l != layer for o in items
                      if SEVERITY_RANK[o.severity] >= 1 and _overlaps(_scope(a), _scope(o))]
            if others or SEVERITY_RANK[a.severity] <= SEVERITY_RANK["warning"]:
                res.forwarded.append(a)
                if others:
                    res.corroborated.append(a.id)
            else:
                res.forwarded.append(a.model_copy(update={"severity": "warning",
                                                          "explanation": f"[uncorroborated {layer} signal, downgraded to warning] {a.explanation}"}))
                res.downgraded.append(a.id)
    n = len(res.layers_alerting)
    res.agreement = "none" if n == 0 else "single" if n == 1 else "partial" if n == 2 else "full"
    return res
