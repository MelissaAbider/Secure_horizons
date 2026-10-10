"""Fallback routers that serve fixtures/ (TASKS.md 2.9). Owner: T0.

backend/main.py mounts one of these ONLY while the owning task's router module does not exist yet:
state (T3, backend/api/state.py), response (T4, backend/api/response.py), incidents (T5, backend/api/incidents.py),
demo (T2, backend/api/demo.py), metrics (T7, backend/api/metrics.py). This lets the dashboard (T6) work
against every route from the first commit. Approve and submit only change an in-memory copy.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend import fixtures, settings
from backend.models import (
    Alert,
    Decision,
    DemoRun,
    Dependency,
    EvalMetrics,
    Health,
    Incident,
    SeriesPoint,
    StateResponse,
    VerifyResult,
)

_memory: dict[str, list] = {}


def _decisions() -> list[Decision]:
    if "decisions" not in _memory:
        _memory["decisions"] = [Decision.model_validate(d) for d in fixtures.load("decisions.json")]
    return _memory["decisions"]


def _incidents() -> list[Incident]:
    if "incidents" not in _memory:
        _memory["incidents"] = [Incident.model_validate(fixtures.load("incident.json"))]
    return _memory["incidents"]


def reset_memory() -> None:
    _memory.clear()


# ---------- state (T3) ----------
state = APIRouter(tags=["state (fixtures)"])


@state.get("/health", response_model=Health)
def health() -> Health:
    return Health.model_validate(fixtures.load("health.json"))


@state.get("/state", response_model=StateResponse)
def get_state() -> StateResponse:
    return StateResponse.model_validate(fixtures.load("state.json"))


@state.get("/series", response_model=list[SeriesPoint])
def series(deployment_id: str = "lend-eth", asset: str = "WETH", limit: int = Query(300, ge=1, le=2000)) -> list[SeriesPoint]:
    points = fixtures.load("series.json").get(f"{deployment_id}:{asset}", [])
    return [SeriesPoint.model_validate(p) for p in points][-limit:]


@state.get("/alerts", response_model=list[Alert])
def alerts(since_block: int = 0) -> list[Alert]:
    return [a for a in (Alert.model_validate(x) for x in fixtures.load("alerts.json")) if a.block_number >= since_block]


# ---------- response (T4) ----------
response = APIRouter(tags=["response (fixtures)"])


class ApproveBody(BaseModel):
    action_index: int
    approver: str = Field(min_length=1)
    approve: bool = True


@response.get("/decisions", response_model=list[Decision])
def decisions() -> list[Decision]:
    return _decisions()


@response.post("/decisions/{decision_id}/approve", response_model=Decision)
def approve(decision_id: str, body: ApproveBody) -> Decision:
    decision = next((d for d in _decisions() if d.id == decision_id), None)
    if decision is None:
        raise HTTPException(404, detail="decision not found")
    if not 0 <= body.action_index < len(decision.actions):
        raise HTTPException(400, detail=f"action_index {body.action_index} out of range")
    action = decision.actions[body.action_index]
    if action.status != "pending_approval":
        raise HTTPException(409, detail=f"action is not pending approval (status={action.status})")
    action.status = "approved" if body.approve else "rejected"
    action.note = f"{'approved' if body.approve else 'rejected'} by {body.approver}; fixture mode, no transaction sent"
    return decision


@response.post("/verify/{decision_id}", response_model=VerifyResult)
def verify(decision_id: str) -> VerifyResult:
    if not any(d.id == decision_id for d in _decisions()):
        raise HTTPException(404, detail="decision not found")
    return VerifyResult.model_validate(fixtures.load("verify.json"))


# ---------- incidents and dependencies (T5) ----------
incidents = APIRouter(tags=["incidents (fixtures)"])


class SubmitBody(BaseModel):
    submitted_by: str = Field(min_length=1)


def _incident(incident_id: str) -> Incident:
    found = next((i for i in _incidents() if i.id == incident_id), None)
    if found is None:
        raise HTTPException(404, detail="incident not found")
    return found


@incidents.get("/incidents", response_model=list[Incident])
def list_incidents() -> list[Incident]:
    return _incidents()


@incidents.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    return _incident(incident_id)


@incidents.get("/incidents/{incident_id}/report.md", response_class=PlainTextResponse)
def report(incident_id: str) -> PlainTextResponse:
    inc = _incident(incident_id)
    return PlainTextResponse(inc.dora.report_markdown if inc.dora else "", media_type="text/markdown")


@incidents.post("/incidents/{incident_id}/submit", response_model=Incident)
def submit(incident_id: str, body: SubmitBody) -> Incident:
    inc = _incident(incident_id)
    if inc.dora is None:
        raise HTTPException(409, detail="no DORA assessment to submit")
    if inc.dora.submitted:
        raise HTTPException(409, detail="already submitted")
    inc.dora.submitted = True
    inc.dora.submitted_by = body.submitted_by
    inc.dora.submitted_at = datetime.now(timezone.utc)
    return inc


@incidents.get("/dependencies", response_model=list[Dependency])
def dependencies() -> list[Dependency]:
    return [Dependency.model_validate(d) for d in fixtures.load("dependencies.json")]


# ---------- demo (T2) ----------
demo = APIRouter(tags=["demo (fixtures)"])


class AttackBody(BaseModel):
    seed: Optional[int] = Field(default=None, ge=0)
    variant: str = Field(default="default", pattern="^(default|slow|usdc)$")


@demo.post("/demo/attack", response_model=DemoRun)
def attack(body: AttackBody) -> DemoRun:
    run = DemoRun.model_validate(fixtures.load("demo_run.json"))
    run.variant = body.variant
    if body.seed is not None:
        run.seed = body.seed
    return run


@demo.post("/demo/reset", response_model=DemoRun)
def reset() -> DemoRun:
    run = DemoRun.model_validate(fixtures.load("demo_run.json"))
    run.kind, run.variant, run.seed, run.params = "reset", None, None, {}
    return run


@demo.get("/demo/runs/{run_id}", response_model=DemoRun)
def get_run(run_id: str) -> DemoRun:
    run = DemoRun.model_validate(fixtures.load("demo_run.json"))
    if run.run_id != run_id:
        raise HTTPException(404, detail="run not found")
    return run


# ---------- metrics (T7) ----------
metrics = APIRouter(tags=["metrics (fixtures)"])


@metrics.get("/metrics", response_model=EvalMetrics)
def get_metrics() -> EvalMetrics:
    path = settings.DATA_DIR / "eval" / "metrics.json"
    if path.exists():
        try:
            return EvalMetrics.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            pass
    return EvalMetrics.model_validate(fixtures.load("metrics.json"))
