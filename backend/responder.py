"""Response matrix: alerts of one snapshot -> one Decision, executed and anchored (TASKS.md 2.8, T4 3.1, 3.2, 3.6)."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from itertools import groupby
from typing import TYPE_CHECKING, Callable

import yaml

from backend import evidence, settings
from backend.models import Action, Alert, Decision, PositionSnapshot, Snapshot
from backend.notify import notify

if TYPE_CHECKING:
    from backend.executor import Executor

logger = logging.getLogger("t4.responder")

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}


def load_playbook() -> tuple[dict, str, str]:
    """(playbook dict, "sha256:<hex of file bytes>", file text). Reloaded on every handle."""
    raw = (settings.CONFIG_DIR / "playbook.yaml").read_bytes()
    text = raw.decode("utf-8")
    return yaml.safe_load(text), "sha256:" + hashlib.sha256(raw).hexdigest(), text


# ---------- Pure functions: no network, disk, clock or env ----------

def deployment_order(snapshot: Snapshot) -> list[str]:
    order: list[str] = []
    for reserve in snapshot.reserves:
        if reserve.deployment_id not in order:
            order.append(reserve.deployment_id)
    return order


def _sort_positions(positions: list[PositionSnapshot], snapshot: Snapshot) -> list[PositionSnapshot]:
    order = deployment_order(snapshot)

    def key(p: PositionSnapshot):
        return (order.index(p.deployment_id) if p.deployment_id in order else len(order), p.asset)

    return sorted(positions, key=key)


def concerned_positions(alert: Alert, snapshot: Snapshot) -> list[PositionSnapshot]:
    held = [p for p in snapshot.positions if int(p.supplied) > 0]
    if alert.rule_id == "R1_BACKING_DROP":
        deployments = {r.deployment_id for r in snapshot.reserves if r.asset == alert.asset and r.ltv_bps > 0}
        found = [p for p in held if p.deployment_id in deployments]
    elif alert.rule_id in ("R2_LIQUIDITY_DROP", "R3_UTILIZATION_HIGH", "R4_POSITION_STUCK"):
        found = [p for p in held if (p.deployment_id, p.asset) == (alert.deployment_id, alert.asset)]
    elif alert.rule_id == "R5_RESERVE_FROZEN":
        found = [p for p in held if p.deployment_id == alert.deployment_id]
    else:
        logger.warning("unknown rule_id %s in alert %s", alert.rule_id, alert.id)
        found = []
    return _sort_positions(found, snapshot)


def _union(groups: list[list[PositionSnapshot]], snapshot: Snapshot) -> list[PositionSnapshot]:
    seen: dict[tuple[str, str], PositionSnapshot] = {}
    for group in groups:
        for p in group:
            seen.setdefault((p.deployment_id, p.asset), p)
    return _sort_positions(list(seen.values()), snapshot)


def assess(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> dict:
    severity = max((a.severity for a in alerts), key=SEVERITY_RANK.__getitem__, default="info")
    exposed = _union([concerned_positions(a, snapshot) for a in alerts], snapshot)
    acted = _union([concerned_positions(a, snapshot) for a in alerts
                    if SEVERITY_RANK[a.severity] >= SEVERITY_RANK["high"]], snapshot)
    exposure_usd = round(sum(p.value_usd for p in exposed), 2)
    withdrawable_usd = round(sum(p.withdrawable_usd for p in exposed), 2)
    exposure_tag = "exposure>=1k" if exposure_usd >= playbook["min_exposure_usd"] else "exposure<1k"
    exit_tag = "exit_possible" if withdrawable_usd > 0 else "no_liquidity"
    return {
        "severity": severity,
        "positions": acted,
        "exposure_usd": exposure_usd,
        "withdrawable_usd": withdrawable_usd,
        "matrix_cell": f"{severity}|{exposure_tag}|{exit_tag}",
    }


def plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]:
    """PURE. Reused as is by verify: params never change after planning."""
    if not alerts:
        return []
    result = assess(alerts, snapshot, playbook)
    severity = result["severity"]
    if result["exposure_usd"] < playbook["min_exposure_usd"]:
        threshold = playbook["below_min_exposure"]["notify_if_severity_at_least"]
        if SEVERITY_RANK[severity] >= SEVERITY_RANK[threshold]:
            return [Action(type="NOTIFY", mode="auto", status="planned")]
        return []
    actions: list[Action] = []
    for entry in playbook["matrix"].get(severity) or []:
        mode = entry["mode"]
        status = "planned" if mode == "auto" else "pending_approval"
        if entry.get("per_position"):
            for p in result["positions"]:
                if int(p.withdrawable_now) > 0:
                    actions.append(Action(type=entry["type"], mode=mode, status=status,
                                          params={"deployment_id": p.deployment_id, "asset": p.asset}))
        elif entry["type"] == "PAUSE_DEPOSITS" and snapshot.vault.deposits_paused:
            actions.append(Action(type="PAUSE_DEPOSITS", mode=mode, status="skipped", note="already paused"))
        else:
            actions.append(Action(type=entry["type"], mode=mode, status=status))
    return actions


def rationale(decision_fields: dict) -> str:
    """decision_fields: severity, rule_ids, exposure_usd, actions."""
    actions = decision_fields["actions"]
    n_auto = sum(a.mode == "auto" for a in actions)
    n_human = sum(a.mode == "human" for a in actions)
    rule_ids = ", ".join(sorted(set(decision_fields["rule_ids"])))
    return (f"{decision_fields['severity']} alert(s) {rule_ids} with ${decision_fields['exposure_usd']:,.0f} exposed: "
            f"{n_auto} automatic action(s), {n_human} awaiting approval.")


# ---------- Responder ----------

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class Responder:
    def __init__(self, store, executor: "Executor"):
        self.store = store
        self.executor = executor
        self._handlers: list[Callable[[list[Decision], list[Alert], Snapshot], None]] = []
        self._seen_alert_ids: set[str] = {aid for d in store.decisions() for aid in d.alert_ids}
        self._generation = store.generation

    def on_decisions(self, handler: Callable[[list[Decision], list[Alert], Snapshot], None]) -> None:
        self._handlers.append(handler)

    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> list[Decision]:
        """Never raises: the engine calls it from a thread, one snapshot at a time."""
        try:
            return self._handle(alerts, snapshot)
        except Exception:  # noqa: BLE001
            logger.exception("responder failed on block %s", snapshot.block_number)
            return []

    def _handle(self, alerts: list[Alert], snapshot: Snapshot) -> list[Decision]:
        if self.store.generation != self._generation:
            self._seen_alert_ids.clear()
            self._generation = self.store.generation
        new = sorted((a for a in alerts if a.id not in self._seen_alert_ids), key=lambda a: a.id)
        if not new:
            return []
        playbook, playbook_version, playbook_text = load_playbook()
        actions = plan_actions(new, snapshot, playbook)
        if not actions:
            return []

        result = assess(new, snapshot, playbook)
        n = 1 + sum(d.block_number == snapshot.block_number for d in self.store.decisions())
        decision = Decision(
            id=f"DEC-{snapshot.network}-{snapshot.block_number}-{n}",
            created_at=_now(),
            network=snapshot.network,
            block_number=snapshot.block_number,
            alert_ids=[a.id for a in new],
            severity=result["severity"],
            exposure_usd=result["exposure_usd"],
            withdrawable_usd=result["withdrawable_usd"],
            exit_cost_bps=0,
            matrix_cell=result["matrix_cell"],
            rationale=rationale({"severity": result["severity"], "rule_ids": [a.rule_id for a in new],
                                 "exposure_usd": result["exposure_usd"], "actions": actions}),
            actions=actions,
            inputs_hash=evidence.inputs_hash(new, snapshot),
            rules_version=new[0].rules_version,
            playbook_version=playbook_version,
        )
        positions = {(p.deployment_id, p.asset): p for p in snapshot.positions}
        executed = [self._execute(a, decision, new, positions) for a in actions]
        decision = decision.model_copy(update={"actions": executed})
        decision = decision.model_copy(update={"record_hash": evidence.record_hash(decision)})

        evidence.write_evidence(decision, new, snapshot, playbook_text)
        try:
            decision = evidence.anchor_decision(decision, self.executor)
        except Exception:  # noqa: BLE001
            logger.exception("anchoring failed for %s", decision.id)
            decision = decision.model_copy(update={"anchor_tx": None, "anchor_block": None})
        evidence.write_evidence(decision, new, snapshot, playbook_text)
        self.store.add_decision(decision)
        self._seen_alert_ids.update(a.id for a in new)
        self._log(decision)

        for handler in self._handlers:
            try:
                handler([decision], new, snapshot)
            except Exception:  # noqa: BLE001
                logger.exception("decision handler failed for %s", decision.id)
        return [decision]

    def _execute(self, action: Action, decision: Decision, alerts: list[Alert],
                 positions: dict[tuple[str, str], PositionSnapshot]) -> Action:
        if action.mode != "auto" or action.status != "planned":
            return action
        try:
            if action.type == "NOTIFY":
                channels = notify(decision, alerts)
                return action.model_copy(update={"status": "executed", "executed_at": _now(),
                                                 "note": "channels: " + ",".join(channels)})
            if action.type == "OPEN_INCIDENT":
                return action.model_copy(update={"status": "executed", "executed_at": _now(),
                                                 "note": "delegated to incident manager"})
            if action.type == "PAUSE_DEPOSITS":
                res = self.executor.pause_deposits()
            elif action.type == "UNPAUSE_DEPOSITS":
                res = self.executor.unpause_deposits()
            elif action.type == "EMERGENCY_WITHDRAW":
                dep, asset = action.params["deployment_id"], action.params["asset"]
                res = self.executor.emergency_withdraw(dep, asset)
                if res["status"] == "executed" and not res.get("amount") and (dep, asset) in positions:
                    res = {**res, "amount": positions[(dep, asset)].withdrawable_now}
            else:
                return action.model_copy(update={"status": "skipped", "note": f"no executor for {action.type}"})
        except Exception as e:  # noqa: BLE001
            logger.exception("action %s failed", action.type)
            return action.model_copy(update={"status": "failed", "executed_at": _now(),
                                             "note": f"{type(e).__name__}: {e}"[:200]})
        return action.model_copy(update={"status": res["status"], "tx_hash": res.get("tx_hash"),
                                         "amount": res.get("amount"), "note": res.get("note"),
                                         "executed_at": _now()})

    @staticmethod
    def _log(decision: Decision) -> None:
        names: list[str] = []
        for (kind, pending), group in groupby(decision.actions, key=lambda a: (a.type, a.status == "pending_approval")):
            count = len(list(group))
            names.append(kind + (f"x{count}" if count > 1 else "") + ("(pending)" if pending else ""))
        logger.info("DECISION %s %s exposure=$%s cell=%s actions=%s", decision.id, decision.severity,
                    f"{decision.exposure_usd:,.0f}", decision.matrix_cell, ",".join(names))
        for a in decision.actions:
            logger.info("ACTION %s %s %s tx=%s amount=%s", a.type, a.params, a.status, a.tx_hash, a.amount)
