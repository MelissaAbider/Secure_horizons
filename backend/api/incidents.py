"""T5 routes (TASKS.md 2.9, T5 9): incidents, DORA report, submit, dependencies.

settings.USE_FIXTURES is read on every request. Live mode: IncidentManager(store) and refresh before each read.
Errors are always {"detail": "..."}.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend import settings
from backend.incidents import IncidentManager, dependency_statuses
from backend.models import Dependency, Incident

router = APIRouter(tags=["incidents"])

NOT_FOUND = "incident not found"


class SubmitBody(BaseModel):
    submitted_by: str = Field(min_length=1)


def get_store():
    """The shared store (backend/store.py, T0). Tests override this dependency."""
    from backend.store import store

    return store


def _fixture(name: str):
    path = settings.FIXTURES_DIR / name
    if not path.exists():
        raise HTTPException(503, detail=f"fixture {name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_incident(incident_id: str) -> Incident:
    incident = Incident.model_validate(_fixture("incident.json"))
    if incident.id != incident_id:
        raise HTTPException(404, detail=NOT_FOUND)
    return incident


def _live_incident(store, incident_id: str) -> Incident:
    incident = IncidentManager(store).refresh(incident_id)
    if incident is None:
        raise HTTPException(404, detail=NOT_FOUND)
    return incident


@router.get("/incidents", response_model=list[Incident])
def list_incidents(store=Depends(get_store)) -> list[Incident]:
    if settings.USE_FIXTURES:
        return [Incident.model_validate(_fixture("incident.json"))]
    manager = IncidentManager(store)
    incidents = [manager.refresh(i.id) or i for i in store.incidents()]
    return sorted(incidents, key=lambda i: i.opened_at, reverse=True)


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str, store=Depends(get_store)) -> Incident:
    if settings.USE_FIXTURES:
        return _fixture_incident(incident_id)
    return _live_incident(store, incident_id)


@router.get("/incidents/{incident_id}/report.md", response_class=PlainTextResponse)
def get_report(incident_id: str, store=Depends(get_store)) -> PlainTextResponse:
    incident = _fixture_incident(incident_id) if settings.USE_FIXTURES else _live_incident(store, incident_id)
    if incident.dora is None:
        raise HTTPException(409, detail="incident has no DORA assessment")
    return PlainTextResponse(incident.dora.report_markdown, media_type="text/markdown; charset=utf-8")


@router.post("/incidents/{incident_id}/submit", response_model=Incident)
def submit(incident_id: str, body: SubmitBody, store=Depends(get_store)) -> Incident:
    if settings.USE_FIXTURES:
        incident = _fixture_incident(incident_id)
        if incident.dora is None:
            raise HTTPException(409, detail="incident has no DORA assessment")
        incident.dora.submitted, incident.dora.submitted_by = True, body.submitted_by
        return incident
    try:
        return IncidentManager(store).submit(incident_id, body.submitted_by)
    except KeyError:
        raise HTTPException(404, detail=NOT_FOUND) from None
    except ValueError as e:
        raise HTTPException(409, detail=str(e)) from None


@router.get("/dependencies", response_model=list[Dependency])
def list_dependencies(store=Depends(get_store)) -> list[Dependency]:
    if settings.USE_FIXTURES:
        return [Dependency.model_validate(d) for d in _fixture("dependencies.json")]
    return dependency_statuses(store)
