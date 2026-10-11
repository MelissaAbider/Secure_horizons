"""Detection-only response: T3 alerts -> Discord message; first critical alert -> incident + DORA draft PDF. Owner: T5.

Fund withdrawal (the T4 responder) is out of scope for now: nothing here sends a transaction.
Every figure comes from the T3 alerts and the on-chain snapshot they were raised on.

python -m backend.alerting      run the T3 engine on $NETWORK with this subscriber and print every alert (make watch)
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from backend import dora, notify, settings
from backend.dora_pdf import render_pdf
from backend.models import Alert, DoraAssessment, Incident, NotificationDelivery, Snapshot, TimelineEvent

log = logging.getLogger("backend.alerting")
NOTIFY_MIN = "high"  # warnings stay on the dashboard, high and critical go to Discord
RANK = notify.SEVERITY_RANK


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _treasury_usd(snapshot: Snapshot) -> float:
    """Vault positions plus idle vault balances, valued at the snapshot prices."""
    vault = snapshot.vault.address.lower()
    positions = sum(p.value_usd for p in snapshot.positions if p.wallet.lower() == vault)
    prices = {t.symbol: (t.price_usd, t.decimals) for t in snapshot.tokens}
    idle = sum(int(v) / 10 ** prices[s][1] * prices[s][0] for s, v in snapshot.vault.idle_balances.items() if s in prices)
    return positions + idle


def _third_parties(alerts: list[Alert]) -> list[str]:
    try:
        from backend import chain

        d = chain.load_deployment()
    except Exception:  # no deployment file (fixture replay): generic names
        return ["rsETH bridge (simulated)", "Lending protocol (simulated)", "Price oracle (simulated)"]
    used = notify.scope(alerts) or {m["id"] for m in d["lending"]}
    out = [f"rsETH bridge, MockBridge {d['contracts']['MockBridge']}"]
    out += [f"{m['label']} ({m['id']}, {m['address']})" for m in d["lending"] if m["id"] in used]
    out.append(f"Price oracle, MockOracle {d['contracts']['MockOracle']}")
    return out


class Alerting:
    """Engine subscriber. One open incident at a time; a new deployment (make reset) or a store reset starts over."""

    def __init__(self, store, post: Callable = notify.post_webhook, profile: Optional[dict] = None):
        self.store = store
        self.post = post
        self.profile = profile
        self.incident_id: Optional[str] = None
        self.alerts: list[Alert] = []
        self.classified_at: Optional[datetime] = None
        self.deployment_key = None
        self.deliveries: list[NotificationDelivery] = []  # every Discord attempt, newest last
        self._lock = threading.Lock()

    # ---------- engine subscriber ----------

    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> Optional[Incident]:
        with self._lock:
            try:
                return self._handle(alerts, snapshot)
            except Exception:
                log.exception("alerting failed for %s", [a.id for a in alerts])
                return None

    def _handle(self, alerts: list[Alert], snapshot: Snapshot) -> Optional[Incident]:
        self._follow_deployment()
        alerts = [a for a in alerts if RANK[a.severity] >= RANK[NOTIFY_MIN]]
        if not alerts:
            return None
        incident = self.store.get_incident(self.incident_id) if self.incident_id else None
        opened = False
        if incident is None and any(a.severity == "critical" for a in alerts):
            self.alerts, self.classified_at, opened = [], _now(), True
            incident = self._new_incident(alerts[0])
        if incident is not None:
            self.alerts += alerts
            incident = self._update(incident, snapshot)
        attach = incident is not None and (opened or any(a.rule_id == "R5_CONTAINMENT" for a in alerts))
        if self._send(alerts, snapshot, incident, attach) and incident is not None:
            sent = TimelineEvent(at=_now(), block_number=snapshot.block_number, kind="action",
                                 text=f"Operations channel alerted on Discord: {', '.join(a.rule_id for a in alerts)}"
                                      + (" (DORA draft attached)" if attach else ""), ref=None)
            incident = self._update(incident.model_copy(update={"timeline": incident.timeline + [sent]}), snapshot)
        return incident

    def _follow_deployment(self) -> None:
        try:
            from backend import chain

            key = chain.load_deployment().get("deployed_at_block")
        except Exception:
            key = None
        if key != self.deployment_key:
            self.deployment_key, self.incident_id, self.alerts = key, None, []

    # ---------- incident and DORA ----------

    def _new_incident(self, first: Alert) -> Incident:
        day = first.detected_at.strftime("%Y%m%d")
        n = 1 + sum(1 for i in self.store.incidents() if i.id.startswith(f"INC-{day}-"))
        now = _now()
        incident = Incident(id=f"INC-{day}-{n:03d}", title=first.title, status="open", severity="critical",
                            opened_at=now, detected_at=first.detected_at, contained_at=None, alert_ids=[],
                            decision_ids=[], exposure_usd=0.0, saved_usd=0.0, at_risk_usd=0.0, dora=None, timeline=[])
        self.incident_id = incident.id
        log.warning("incident %s opened on %s", incident.id, first.id)
        return incident

    def _update(self, incident: Incident, snapshot: Snapshot) -> Incident:
        alerts = self.alerts
        exposure = max(a.exposure_usd for a in alerts)
        known = {e.ref for e in incident.timeline if e.kind == "alert"}
        timeline = incident.timeline + [
            TimelineEvent(at=a.detected_at, block_number=a.block_number, kind="alert",
                          text=f"{a.rule_id} {a.severity}: {a.title}", ref=a.id)
            for a in alerts if a.id not in known]
        incident = incident.model_copy(update={
            "alert_ids": list(dict.fromkeys(a.id for a in alerts)), "exposure_usd": exposure,
            "at_risk_usd": exposure - incident.saved_usd, "timeline": timeline})
        profile = self.profile or dora.load_profile()
        facts = dora.IncidentFacts(exposure_usd=exposure, total_treasury_usd=_treasury_usd(snapshot),
                                   at_risk_usd=incident.at_risk_usd, aware_at=incident.detected_at, end_at=_now(),
                                   deposits_paused_hours=0.0)
        criteria = dora.compute_criteria(facts, profile)
        c = dora.classify(criteria)
        assessment = DoraAssessment(criteria=criteria, thresholds_met=c.thresholds_met, is_major=c.is_major,
                                    legal_basis=c.legal_basis, aware_at=incident.detected_at,
                                    classified_at=self.classified_at or _now(),
                                    deadlines=dora.deadlines(incident.detected_at, self.classified_at or _now()),
                                    report_markdown="", ai_drafted_sections=[], submitted=False, submitted_by=None,
                                    submitted_at=None)
        incident = incident.model_copy(update={"dora": assessment})
        report = dora.render_report(incident, self._description(incident, snapshot), profile, _third_parties(alerts))
        incident = incident.model_copy(update={"dora": assessment.model_copy(update={"report_markdown": report})})
        self.store.upsert_incident(incident)
        path = settings.DATA_DIR / "reports" / f"{incident.id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_pdf(incident, profile))
        return incident

    def _description(self, incident: Incident, snapshot: Snapshot) -> str:
        first = next(a for a in self.alerts if a.severity == "critical")
        value, withdrawable = notify._vault_position_values(snapshot, notify.scope(self.alerts))
        told = ("the operations team was alerted on Discord" if settings.ALERT_WEBHOOK_URL
                else "the alert is shown on the monitoring dashboard")
        later = "; ".join(f"{a.rule_id} {a.severity} at block {a.block_number:,}" for a in self.alerts[1:])
        return (f"At {dora.iso(first.detected_at)} (block {first.block_number:,} on {first.network}) the monitoring "
                f"platform raised {first.rule_id} ({first.severity}): {first.explanation} "
                f"Treasury exposure in the deployments accepting the affected collateral: {dora.fmt_usd(incident.exposure_usd)} USD. "
                f"At block {snapshot.block_number:,}, {dora.fmt_usd(withdrawable)} USD of the "
                f"{dora.fmt_usd(value)} USD of positions concerned could still be withdrawn. "
                f"No automated withdrawal was executed (detection-only mode): {told}."
                + (f" Subsequent signals: {later}." if later else ""))

    # ---------- Discord ----------

    def _send(self, alerts: list[Alert], snapshot: Snapshot, incident: Optional[Incident], attach: bool) -> bool:
        name = f"{incident.id}-DORA-draft.pdf" if attach and incident is not None else None

        def record(status: str, http_status: Optional[int] = None) -> bool:
            self.deliveries = (self.deliveries + [NotificationDelivery(
                at=_now(), channel="discord", status=status, rule_ids=[a.rule_id for a in alerts],
                incident_id=incident.id if incident else None, attachment=name, http_status=http_status)])[-200:]
            return status == "sent"

        url = settings.ALERT_WEBHOOK_URL
        if not url:
            return record("not_configured")
        if not notify.is_discord_webhook(url):
            log.warning("ALERT_WEBHOOK_URL is not a discord.com webhook: message not sent")
            return record("not_configured")
        payload = notify.build_alert_payload(alerts, snapshot, incident)
        file = (name, (settings.DATA_DIR / "reports" / f"{incident.id}.pdf").read_bytes()) if name else None
        try:
            status = self.post(url, payload, file)
        except Exception as exc:
            log.warning("Discord webhook failed (%s)", type(exc).__name__)
            return record("failed")
        if status >= 300:
            log.warning("Discord webhook answered HTTP %s", status)
            return record("failed", status)
        return record("sent", status)


_instance: Optional[Alerting] = None


def get_alerting() -> Alerting:
    """The one subscriber shared by the engine (backend/main.py) and the API (backend/api/incidents.py)."""
    global _instance
    if _instance is None:
        from backend.store import store

        _instance = Alerting(store)
    return _instance


def main() -> None:
    """Run the T3 engine on $NETWORK with the alerting subscriber, printing every alert as it fires."""
    import asyncio

    from backend.engine import Engine
    from backend.store import store

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine, alerting = Engine(store), get_alerting()

    def show(alerts: list[Alert], snapshot: Snapshot) -> None:
        for a in alerts:
            print(f"{_now():%H:%M:%S} ALERT block={a.block_number} {a.rule_id} {a.severity.upper()} "
                  f"{a.deployment_id or 'global'}/{a.asset} exposure=${a.exposure_usd:,.0f} | {a.explanation}", flush=True)

    engine.on_alerts(show)
    engine.on_alerts(alerting.handle)
    host = settings.RPC_URL.split("/")[2] if "//" in settings.RPC_URL else settings.RPC_URL
    discord = "on" if settings.ALERT_WEBHOOK_URL else "off (ALERT_WEBHOOK_URL empty)"
    print(f"watching {settings.NETWORK} ({host}), Discord {discord}, DORA drafts in {settings.DATA_DIR / 'reports'}",
          flush=True)
    asyncio.run(engine.run_forever())


if __name__ == "__main__":
    main()
