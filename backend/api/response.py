"""T4 routes (TASKS.md 2.9, T4 3.7): GET /decisions, POST /decisions/{id}/approve, POST /verify/{decision_id}.

settings.USE_FIXTURES is read on every request. Errors are always {"detail": "..."}.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import evidence, settings
from backend.executor import get_executor
from backend.models import Decision, VerifyResult

router = APIRouter(tags=["response"])
_LOCK = threading.Lock()


class ApproveBody(BaseModel):
    action_index: int
    approver: str = Field(min_length=1)
    approve: bool


def get_store():
    """The shared store (backend/store.py, T0). Tests override this dependency."""
    from backend.store import store

    return store


def _fixture(name: str):
    path = settings.FIXTURES_DIR / name
    if not path.exists():
        raise HTTPException(503, detail=f"fixture {name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/decisions", response_model=list[Decision])
def list_decisions(store=Depends(get_store)) -> list[Decision]:
    if settings.USE_FIXTURES:
        return [Decision.model_validate(d) for d in _fixture("decisions.json")]
    return store.decisions()


def _check(decision: Decision | None, index: int) -> None:
    if decision is None:
        raise HTTPException(404, detail="decision not found")
    if not 0 <= index < len(decision.actions):
        raise HTTPException(400, detail=f"action_index {index} out of range (0..{len(decision.actions) - 1})")
    status = decision.actions[index].status
    if status != "pending_approval":
        raise HTTPException(409, detail=f"action is not pending approval (status={status})")


def _withdrawable_now(ev: dict | None, deployment_id: str, asset: str) -> str | None:
    for p in ((ev or {}).get("inputs") or {}).get("snapshot", {}).get("positions", []):
        if (p.get("deployment_id"), p.get("asset")) == (deployment_id, asset):
            return p.get("withdrawable_now")
    return None


@router.post("/decisions/{decision_id}/approve", response_model=Decision)
def approve(decision_id: str, body: ApproveBody, store=Depends(get_store)) -> Decision:
    if settings.USE_FIXTURES:
        decisions = {d["id"]: Decision.model_validate(d) for d in _fixture("decisions.json")}
        decision = decisions.get(decision_id)
        _check(decision, body.action_index)
        decision.actions[body.action_index].status = "approved" if body.approve else "rejected"
        return decision

    with _LOCK:
        decision = store.get_decision(decision_id)
        _check(decision, body.action_index)
        decision = decision.model_copy(deep=True)
        action = decision.actions[body.action_index]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            ev = evidence.load_local(decision_id)
        except LookupError:
            ev = None

        if not body.approve:
            action.status = "rejected"
            action.note = f"rejected by {body.approver}; no transaction sent"
            action.executed_at = now
        else:
            action.status = "approved"
            executor = get_executor()
            if action.type == "EMERGENCY_WITHDRAW":
                res = executor.emergency_withdraw(action.params["deployment_id"], action.params["asset"])
            elif action.type == "UNPAUSE_DEPOSITS":
                res = executor.unpause_deposits()
            elif action.type == "PAUSE_DEPOSITS":
                res = executor.pause_deposits()
            else:
                res = {"status": "executed", "tx_hash": None, "amount": None, "note": None}
            action.status = res["status"]
            action.tx_hash = res.get("tx_hash")
            action.amount = res.get("amount")
            if action.type == "EMERGENCY_WITHDRAW" and action.status == "executed" and not action.amount:
                action.amount = _withdrawable_now(ev, action.params["deployment_id"], action.params["asset"])
            action.note = f"approved by {body.approver}; {res.get('note') or ''}"
            action.executed_at = now

        store.update_decision(decision)  # record_hash is not recomputed: it freezes the decision as planned
        if ev is not None:
            ev["approvals"].append({"action_index": body.action_index, "approver": body.approver,
                                    "approve": body.approve, "at": now.isoformat().replace("+00:00", "Z"),
                                    "result": action.model_dump(mode="json")})
            evidence.save_evidence(decision_id, ev)
        return decision


@router.post("/verify/{decision_id}", response_model=VerifyResult)
def verify(decision_id: str) -> VerifyResult:
    if settings.USE_FIXTURES:
        return VerifyResult.model_validate({**_fixture("verify.json"), "decision_id": decision_id})
    try:
        return evidence.verify(decision_id)
    except LookupError:
        raise HTTPException(404, detail="decision not found") from None
