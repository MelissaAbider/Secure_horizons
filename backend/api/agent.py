"""Agent routes: POST /agent/propose, GET /agent/proposals. The agent proposes; nothing here executes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import agent

router = APIRouter(tags=["agent"])

RECENT_BLOCKS = 20  # rules window (TASKS.md 2.7): alerts without an incident stay active this long


class ProposeBody(BaseModel):
    message: str = Field(min_length=1, max_length=agent.MAX_MESSAGE)


def get_store():
    from backend.store import store

    return store


def active_alerts(store, block: int) -> list:
    """High/critical alerts not closed by a human: in a non-resolved incident, or recent and without incident."""
    incidents = store.incidents()
    resolved = {a for i in incidents if i.status == "resolved" for a in i.alert_ids}
    tracked = {a for i in incidents if i.status != "resolved" for a in i.alert_ids}
    return [a for a in store.alerts(0) if a.severity in ("high", "critical") and a.id not in resolved
            and (a.id in tracked or a.block_number >= block - RECENT_BLOCKS)]


@router.post("/agent/propose")
def propose(body: ProposeBody, store=Depends(get_store)) -> dict:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(503, detail="no snapshot yet")
    return agent.run(body.message, snapshot, active_alerts(store, snapshot.block_number))


@router.get("/agent/proposals")
def proposals() -> list[dict]:
    return agent.list_records()
