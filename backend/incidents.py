"""Incident manager: decisions -> one tracked incident with amounts, status, DORA and timeline (TASKS.md T5 7, 8).

All state lives in the store: the manager can be instantiated twice (main.py, API) without diverging.
Decisions are never modified: the link decision -> incident is Incident.decision_ids.
"""
from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Iterable

import yaml

from backend import llm, settings
from backend.dora import (
    IncidentFacts, classify, compute_criteria, deadlines, fmt_tokens, fmt_usd, iso, load_profile, render_report,
    short_label, template_description,
)
from backend.models import (
    Action, Alert, Decision, Dependency, DoraAssessment, Incident, ReserveSnapshot, Snapshot, TimelineEvent,
)

logger = logging.getLogger("t5.incidents")

CONTAINMENT_SNAPSHOTS = 10
MIN_EXPOSURE_USD = 1000
SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
SNAPSHOT_LIMIT = 2000
HUMAN_NOTE = re.compile(r"(approved|rejected) by ([^;]+)")
CHANNELS_NOTE = re.compile(r"channels: ([^;]+)")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def concerned_positions(alert: Alert, snapshot: Snapshot) -> set[tuple[str, str]]:
    """(deployment_id, asset) of the vault positions concerned by an alert (2.8)."""
    if alert.rule_id == "R1_BACKING_DROP":
        deployments = {r.deployment_id for r in snapshot.reserves if r.asset == alert.asset and r.ltv_bps > 0}
        return {(p.deployment_id, p.asset) for p in snapshot.positions if p.deployment_id in deployments}
    if alert.rule_id in ("R2_LIQUIDITY_DROP", "R3_UTILIZATION_HIGH", "R4_POSITION_STUCK"):
        return {(alert.deployment_id, alert.asset)}
    if alert.rule_id == "R5_RESERVE_FROZEN":
        return {(p.deployment_id, p.asset) for p in snapshot.positions if p.deployment_id == alert.deployment_id}
    return set()


def _withdrawals(decision: Decision) -> Iterable[Action]:
    return (a for a in decision.actions if a.type == "EMERGENCY_WITHDRAW")


def _reserve(snapshot: Snapshot, deployment_id: str, asset: str) -> ReserveSnapshot | None:
    return next((r for r in snapshot.reserves if (r.deployment_id, r.asset) == (deployment_id, asset)), None)


def _opens_incident(decision: Decision) -> bool:
    return any(a.type == "OPEN_INCIDENT" and a.status != "failed" for a in decision.actions)


class IncidentManager:
    def __init__(self, store, *, llm_async: bool = True, profile: dict | None = None):
        self.store = store
        self.llm_async = llm_async
        self.profile = profile or load_profile()
        self._lock = threading.RLock()
        self._inflight: set[str] = set()

    # ---------- entry points ----------

    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None:
        """Called by the responder (engine thread). Never raises."""
        try:
            with self._lock:
                return self._handle(decisions, alerts, snapshot)
        except Exception:  # noqa: BLE001
            logger.exception("handle failed block=%s", snapshot.block_number)
            return None

    def refresh(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._refresh(incident_id)

    def submit(self, incident_id: str, submitted_by: str) -> Incident:
        """KeyError if unknown; ValueError("already submitted") or ValueError("incident has no DORA assessment")."""
        with self._lock:
            incident = self.store.get_incident(incident_id)
            if incident is None:
                raise KeyError(incident_id)
            incident = self._refresh(incident_id) or incident
            if incident.dora is None:
                raise ValueError("incident has no DORA assessment")
            if incident.dora.submitted:
                raise ValueError("already submitted")
            now = _now()
            dora = incident.dora.model_copy(update={
                "submitted": True, "submitted_by": submitted_by, "submitted_at": now,
                "deadlines": deadlines(incident.dora.aware_at, incident.dora.classified_at, now)})
            self.store.upsert_incident(incident.model_copy(update={"dora": dora}))
            logger.info("submitted id=%s by=%s", incident_id, submitted_by)
            return self._refresh(incident_id, rerender_submitted=True)

    # ---------- handle ----------

    def _handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None:
        extra = [] if any(s.block_number == snapshot.block_number for s in self.store.snapshots(limit=SNAPSHOT_LIMIT)) \
            else [snapshot]
        current = max((i for i in self.store.incidents() if i.status != "resolved"),
                      key=lambda i: i.opened_at, default=None)
        if current is None:
            attached = {d for i in self.store.incidents() for d in i.decision_ids}
            opener = next((d for d in decisions if d.id not in attached and _opens_incident(d)), None)
            if opener is None:
                return None
            self._store_inputs(decisions, alerts)
            current = self._open(opener, decisions, alerts, snapshot)
        elif decisions or alerts:
            self._store_inputs(decisions, alerts)
            current = current.model_copy(update={
                "decision_ids": list(dict.fromkeys(current.decision_ids + [d.id for d in decisions])),
                "alert_ids": list(dict.fromkeys(current.alert_ids + [a.id for a in alerts]))})
            self.store.upsert_incident(current)
        return self._refresh(current.id, extra=extra)

    def _store_inputs(self, decisions: list[Decision], alerts: list[Alert]) -> None:
        known = {a.id for a in self.store.alerts(0)}
        missing = [a for a in alerts if a.id not in known]
        if missing:
            self.store.add_alerts(missing)
        for d in decisions:
            if self.store.get_decision(d.id) is None:
                self.store.add_decision(d)

    def _open(self, opener: Decision, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident:
        prefix = f"INC-{opener.created_at.astimezone(timezone.utc):%Y%m%d}-"
        n = 1 + sum(i.id.startswith(prefix) for i in self.store.incidents())
        own = [a for a in alerts if a.id in opener.alert_ids] or alerts
        pairs = set().union(*(concerned_positions(a, snapshot) for a in alerts)) if alerts else set()
        pairs |= {(a.params["deployment_id"], a.params["asset"]) for d in decisions for a in _withdrawals(d)}
        deployments = sorted({dep for dep, _ in pairs})
        title = own[0].title if own else f"Decision {opener.id}"
        incident = Incident(
            id=f"{prefix}{n:03d}",
            title=f"{title} ({', '.join(deployments)})" if deployments else title,
            status="open",
            severity=max((a.severity for a in alerts), key=SEVERITY_RANK.__getitem__, default=opener.severity),
            opened_at=opener.created_at,
            detected_at=min((a.detected_at for a in alerts), default=opener.created_at),
            alert_ids=list(dict.fromkeys(a.id for a in alerts)),
            decision_ids=list(dict.fromkeys(d.id for d in decisions)),
            exposure_usd=0.0, saved_usd=0.0, at_risk_usd=0.0,
        )
        self.store.upsert_incident(incident)
        logger.info("opened id=%s decision=%s exposure_usd=%s", incident.id, opener.id, opener.exposure_usd)
        return incident

    # ---------- refresh ----------

    def _refresh(self, incident_id: str, extra: list[Snapshot] | None = None,
                 rerender_submitted: bool = False) -> Incident | None:
        old = self.store.get_incident(incident_id)
        if old is None:
            return None
        if old.status == "resolved":
            return old
        snaps = {s.block_number: s for s in self.store.snapshots(limit=SNAPSHOT_LIMIT)}
        for s in extra or []:
            snaps.setdefault(s.block_number, s)
        series = [snaps[b] for b in sorted(snaps)]
        if not series:
            return old
        latest = series[-1]

        def snap_at(block: int) -> Snapshot:
            below = [s for s in series if s.block_number <= block]
            return below[-1] if below else latest

        by_id = {a.id: a for a in self.store.alerts(0)}
        alerts = [by_id[i] for i in old.alert_ids if i in by_id]
        decisions = [d for d in (self.store.get_decision(i) for i in old.decision_ids) if d is not None]

        # saved_usd: executed emergency withdrawals, valued at the decision snapshot
        saved = 0.0
        for d in decisions:
            s = snap_at(d.block_number)
            for a in _withdrawals(d):
                r = _reserve(s, a.params.get("deployment_id"), a.params.get("asset"))
                if a.status == "executed" and a.amount and r:
                    saved += int(a.amount) / 10 ** r.decimals * r.price_usd

        # exposure_usd: concerned positions, valued where each one becomes concerned
        concerned: dict[tuple[str, str], float] = {}

        def add(pairs: Iterable[tuple[str, str]], s: Snapshot) -> None:
            for pair in sorted(pairs):
                if pair not in concerned:
                    concerned[pair] = next((p.value_usd for p in s.positions
                                            if (p.deployment_id, p.asset) == pair), 0.0)

        for a in alerts:
            s = snap_at(a.block_number)
            add(concerned_positions(a, s), s)
        for d in decisions:
            s = snap_at(d.block_number)
            add({(a.params["deployment_id"], a.params["asset"]) for a in _withdrawals(d)}, s)

        latest_positions = {(p.deployment_id, p.asset): p for p in latest.positions}
        at_risk = sum(max(0.0, latest_positions[k].value_usd - latest_positions[k].withdrawable_usd)
                      for k in concerned if k in latest_positions)

        # status
        status, contained_at, contained_block = "open", None, None
        relevant = [a for a in alerts if a.severity in ("high", "critical") and a.exposure_usd >= MIN_EXPOSURE_USD]
        if relevant:
            last = max(a.block_number for a in relevant)
            after = [s for s in series if s.block_number > last]

            def safe(s: Snapshot) -> bool:
                return all(int(p.withdrawable_now) >= int(p.supplied) for p in s.positions
                           if (p.deployment_id, p.asset) in concerned)

            if len(after) >= CONTAINMENT_SNAPSHOTS and safe(after[-1]):
                k = len(after) - 1
                while k > 0 and safe(after[k - 1]):
                    k -= 1
                first = after[max(k, CONTAINMENT_SNAPSHOTS - 1)]
                status, contained_at, contained_block = "contained", first.block_time, first.block_number
        if status != old.status:
            logger.info("status id=%s from=%s to=%s at=%s", old.id, old.status, status, iso(contained_at))

        incident = old.model_copy(update={
            "status": status, "contained_at": contained_at,
            "severity": max((a.severity for a in alerts), key=SEVERITY_RANK.__getitem__, default=old.severity),
            "saved_usd": round(saved, 2), "exposure_usd": round(sum(concerned.values()), 2),
            "at_risk_usd": round(at_risk, 2)})

        # DORA (frozen once submitted)
        dora = old.dora
        if dora is None or not dora.submitted:
            dora = self._assess(incident, decisions, series, snap_at, latest)
        incident = incident.model_copy(update={"dora": dora})
        incident = incident.model_copy(update={
            "timeline": self._timeline(incident, alerts, decisions, series, snap_at, concerned, contained_block)})

        if not dora.submitted or rerender_submitted:
            first_alert = next((a for a in alerts), None)
            third = self._third_parties(alerts, concerned, latest)
            template = template_description(incident, first_alert)
            text, ai = self._description(incident, alerts, decisions, template)
            dora = dora.model_copy(update={"ai_drafted_sections": ["Description"] if ai else []})
            incident = incident.model_copy(update={"dora": dora})
            report = render_report(incident, description=text, profile=self.profile, third_parties=third,
                                   alert=first_alert)
            incident = incident.model_copy(update={"dora": dora.model_copy(update={"report_markdown": report})})

        if incident.model_dump() != old.model_dump():
            self.store.upsert_incident(incident)
        return incident

    def _assess(self, incident: Incident, decisions: list[Decision], series: list[Snapshot], snap_at,
                latest: Snapshot) -> DoraAssessment:
        prev = incident.dora
        pauses = sorted(a.executed_at for d in decisions for a in d.actions
                        if a.type == "PAUSE_DEPOSITS" and a.status == "executed" and a.executed_at)
        paused_hours = 0.0
        if pauses:
            unpauses = sorted(a.executed_at for d in decisions for a in d.actions if a.type == "UNPAUSE_DEPOSITS"
                              and a.status == "executed" and a.executed_at and a.executed_at >= pauses[0])
            end = unpauses[0] if unpauses else latest.block_time
            paused_hours = max(0.0, (end - pauses[0]).total_seconds() / 3600)

        opening = snap_at(decisions[0].block_number) if decisions else latest
        prices = {t.symbol: (t.price_usd, t.decimals) for t in opening.tokens}
        idle = sum(int(units) / 10 ** prices[sym][1] * prices[sym][0]
                   for sym, units in opening.vault.idle_balances.items() if sym in prices)
        total = sum(p.value_usd for p in opening.positions) + idle

        facts = IncidentFacts(exposure_usd=incident.exposure_usd, total_treasury_usd=total,
                              at_risk_usd=incident.at_risk_usd, aware_at=incident.detected_at,
                              end_at=incident.contained_at or latest.block_time, deposits_paused_hours=paused_hours)
        criteria = compute_criteria(facts, self.profile)
        result = classify(criteria)
        classified_at = prev.classified_at if prev else incident.opened_at
        if prev and not prev.is_major and result.is_major:
            classified_at = latest.block_time
        if prev is None or prev.thresholds_met != result.thresholds_met or prev.is_major != result.is_major:
            logger.info("classified id=%s major=%s thresholds=%s", incident.id, str(result.is_major).lower(),
                        ",".join(dict.fromkeys(short_label(t) for t in result.thresholds_met)))
        return DoraAssessment(
            criteria=criteria, thresholds_met=result.thresholds_met, is_major=result.is_major,
            legal_basis=result.legal_basis, aware_at=incident.detected_at, classified_at=classified_at,
            deadlines=deadlines(incident.detected_at, classified_at), report_markdown="",
            ai_drafted_sections=prev.ai_drafted_sections if prev else [],
        )

    # ---------- timeline ----------

    @staticmethod
    def _action_text(incident: Incident, a: Action, s: Snapshot) -> str:
        if a.type == "NOTIFY":
            m = CHANNELS_NOTE.search(a.note or "")
            if not m:
                return "Notification sent"
            return "Notification sent (" + ", ".join(c.strip() for c in m.group(1).split(",") if c.strip()) + ")"
        if a.type == "PAUSE_DEPOSITS":
            return "Deposits paused"
        if a.type == "UNPAUSE_DEPOSITS":
            return "Deposits unpaused"
        if a.type == "OPEN_INCIDENT":
            return f"Incident {incident.id} opened"
        dep, asset = a.params.get("deployment_id"), a.params.get("asset")
        if a.type == "EMERGENCY_WITHDRAW":
            r = _reserve(s, dep, asset)
            amount = a.amount or "0"
            if r is None:
                return f"Emergency withdrawal: {amount} base units of {asset} from {dep} to the vault"
            usd = int(amount) / 10 ** r.decimals * r.price_usd
            return (f"Emergency withdrawal: {fmt_tokens(amount, r.decimals)} {asset} from {dep} to the vault "
                    f"({fmt_usd(usd)} USD)")
        return f"{a.type} executed" + (f" on {dep}" if dep else "")

    def _timeline(self, incident: Incident, alerts: list[Alert], decisions: list[Decision], series: list[Snapshot],
                  snap_at, concerned: dict, contained_block: int | None) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for a in alerts:
            events.append(TimelineEvent(at=a.detected_at, block_number=a.block_number, kind="alert",
                                        text=f"{a.rule_id} {a.severity}: {a.title}", ref=a.id))
        for d in decisions:
            events.append(TimelineEvent(at=d.created_at, block_number=d.block_number, kind="decision",
                                        text=f"Decision {d.id}: {d.matrix_cell}", ref=d.id))
            s = snap_at(d.block_number)
            for a in d.actions:
                at = a.executed_at or d.created_at
                if a.status == "executed":
                    text = self._action_text(incident, a, s)
                    if a.tx_hash and a.tx_hash.startswith("0xdry"):
                        text += " (dry run)"
                    events.append(TimelineEvent(at=at, block_number=d.block_number, kind="action", text=text,
                                                ref=a.tx_hash or d.id))
                elif a.status == "failed":
                    events.append(TimelineEvent(at=at, block_number=d.block_number, kind="action",
                                                text=f"{a.type} failed: {a.note or 'no reason given'}", ref=d.id))
                if a.status == "pending_approval":
                    events.append(TimelineEvent(at=d.created_at, block_number=d.block_number, kind="human",
                                                text=f"Awaiting human approval: {a.type}", ref=d.id))
                elif a.mode == "human" or a.status in ("approved", "rejected"):
                    m = HUMAN_NOTE.search(a.note or "")
                    if m:
                        events.append(TimelineEvent(at=at, block_number=d.block_number, kind="human",
                                                    text=f"{a.type} {m.group(1)} by {m.group(2).strip()}", ref=d.id))
        for dep, asset in sorted(concerned):
            for s in series:
                r = _reserve(s, dep, asset)
                if r is not None and r.available_liquidity == "0":
                    events.append(TimelineEvent(at=s.block_time, block_number=s.block_number, kind="chain",
                                                text=f"{asset} liquidity on {dep} reaches zero", ref=None))
                    break
        dora = incident.dora
        if dora is not None:
            labels = ", ".join(dict.fromkeys(short_label(t) for t in dora.thresholds_met)) or "none"
            events.append(TimelineEvent(at=dora.classified_at, kind="dora", ref=incident.id,
                                        block_number=decisions[0].block_number if decisions else None,
                                        text=f"DORA classification proposed: {'major' if dora.is_major else 'not major'} "
                                             f"({labels})"))
            if dora.submitted and dora.submitted_at:
                events.append(TimelineEvent(at=dora.submitted_at, kind="human", ref=incident.id,
                                            text=f"DORA initial notification submitted by {dora.submitted_by}"))
        if incident.contained_at:
            events.append(TimelineEvent(at=incident.contained_at, block_number=contained_block, kind="decision",
                                        text="Incident contained: no exposed position left", ref=incident.id))
        return sorted(events, key=lambda e: (e.at, e.block_number or 0))

    # ---------- report helpers ----------

    @staticmethod
    def _third_parties(alerts: list[Alert], concerned: dict, latest: Snapshot) -> list[str]:
        order = list(dict.fromkeys(r.deployment_id for r in latest.reserves))
        deployments = sorted({dep for dep, _ in concerned}, key=lambda d: order.index(d) if d in order else len(order))
        bridged = ["rseth"] if any(a.asset == "rsETH" for a in alerts) else []
        return bridged + deployments + ["oracle"]

    def _description(self, incident: Incident, alerts: list[Alert], decisions: list[Decision],
                     template: str) -> tuple[str, bool]:
        if not llm.enabled():
            return template, False
        facts = {
            "id": incident.id, "title": incident.title, "rule_ids": sorted({a.rule_id for a in alerts}),
            "severity": incident.severity, "aware_at": iso(incident.detected_at),
            "exposure_usd": incident.exposure_usd, "saved_usd": incident.saved_usd,
            "at_risk_usd": incident.at_risk_usd, "status": incident.status,
            "actions": [{"type": a.type, "asset": a.params.get("asset"), "deployment_id": a.params.get("deployment_id")}
                        for d in decisions for a in d.actions if a.status == "executed"],
        }
        hit = llm.cached(facts)
        if hit is not None:
            return hit, True
        if not self.llm_async:
            return llm.draft_description(facts, template)
        key = llm.facts_key(facts)
        if key not in self._inflight:
            self._inflight.add(key)
            generation = self.store.generation

            def run() -> None:
                try:
                    _, ai = llm.draft_description(facts, template)
                    if ai and self.store.generation == generation:
                        self.refresh(incident.id)
                except Exception:  # noqa: BLE001
                    logger.exception("background drafting failed id=%s", incident.id)
                finally:
                    self._inflight.discard(key)

            threading.Thread(target=run, daemon=True).start()
        return template, False


# ---------- third-party register ----------

def _status(check: str, dep_id: str, latest: Snapshot | None, now: datetime) -> str:
    if check == "none":
        return "unknown"
    if check == "llm":
        return llm.last_status()
    if latest is None:
        return "unknown"
    if check == "freshness":
        age = (now - latest.block_time).total_seconds()
        return "ok" if age <= 30 else "degraded" if age <= 120 else "down"
    if check == "oracle":
        prices = [r.price_usd for r in latest.reserves] + [t.price_usd for t in latest.tokens]
        return "ok" if prices and all(p > 0 for p in prices) else "degraded"
    if check == "protocol":
        reserves = [r for r in latest.reserves if r.deployment_id == dep_id]
        if not reserves:
            return "unknown"
        if any(r.paused for r in reserves):
            return "down"
        stuck = any(p.withdrawable_ratio_bps < 10000 for p in latest.positions if p.deployment_id == dep_id)
        return "degraded" if stuck or any(r.frozen for r in reserves) else "ok"
    if check == "bridge":
        token = next((t for t in latest.tokens if t.backing_ratio_bps is not None), None)
        if token is None:
            return "unknown"
        return "ok" if token.backing_ratio_bps >= 9900 else "degraded" if token.backing_ratio_bps >= 5000 else "down"
    return "unknown"


def dependency_statuses(store, now: datetime | None = None) -> list[Dependency]:
    now = now or _now()
    latest = store.latest_snapshot()
    entries = yaml.safe_load((settings.CONFIG_DIR / "dependencies.yaml").read_text(encoding="utf-8"))
    result = []
    for entry in entries:
        entry = dict(entry)
        check = entry.pop("check", "none")
        result.append(Dependency(**entry, status=_status(check, entry["id"], latest, now)))
    return result
