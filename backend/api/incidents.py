"""Incident routes (TASKS.md 2.9) for the detection-only mode: incidents, DORA draft download, Discord deliveries.
Owner: T5. The incidents are opened by backend/alerting.py from the live T3 alerts.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from backend import fixtures, settings
from backend.models import Incident, NotificationDelivery

router = APIRouter()


def _incident(incident_id: str) -> Incident:
    from backend.store import store

    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    return incident


@router.get("/incidents", response_model=list[Incident])
def list_incidents():
    if settings.USE_FIXTURES:
        return [fixtures.load("incident.json")]
    from backend.store import store

    return sorted(store.incidents(), key=lambda i: i.opened_at, reverse=True)


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    if settings.USE_FIXTURES:
        return fixtures.load("incident.json")
    return _incident(incident_id)


@router.get("/incidents/{incident_id}/report.md", response_class=PlainTextResponse)
def incident_report(incident_id: str):
    incident = _incident(incident_id)
    if incident.dora is None:
        raise HTTPException(404, "no DORA assessment yet")
    return incident.dora.report_markdown


@router.get("/incidents/{incident_id}/report.pdf")
def incident_pdf(incident_id: str):
    _incident(incident_id)
    path = settings.DATA_DIR / "reports" / f"{incident_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "DORA draft not written yet")
    return FileResponse(path, media_type="application/pdf", filename=f"{incident_id}-DORA-draft.pdf")


@router.get("/notifications", response_model=list[NotificationDelivery])
def notifications():
    """Discord attempts, newest first; status not_configured when ALERT_WEBHOOK_URL is empty."""
    from backend.alerting import get_alerting

    return list(reversed(get_alerting().deliveries))


@router.get("/notifications/config")
def notifications_config() -> dict:
    """Whether a Discord webhook (or the bot that sends the withdraw buttons) is configured. Secrets are never returned."""
    from backend import discord_actions

    return {"discord_configured": bool(settings.ALERT_WEBHOOK_URL) or discord_actions.bot_configured(),
            "network": settings.NETWORK,
            "explorer_url": settings.EXPLORER_URL}
