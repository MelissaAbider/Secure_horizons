# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""FastAPI app: T4 + T5 routes under /api, wired to the stub engine (TASKS.md 2.9, 2.11).

Run with a single uvicorn worker only: the store, the executor and the wiring are in-process singletons.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import settings
from backend.api import agent as agent_api
from backend.api import incidents as incidents_api
from backend.api import response as response_api
from backend.engine import Engine
from backend.executor import get_executor
from backend.incidents import IncidentManager
from backend.responder import Responder
from backend.store import store


def wire(store) -> tuple[Engine, Responder, IncidentManager]:
    engine = Engine(store)
    responder = Responder(store, get_executor())
    incidents = IncidentManager(store)
    engine.on_alerts(responder.handle)
    responder.on_decisions(incidents.handle)
    return engine, responder, incidents


engine, responder, incidents = wire(store)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(engine.run_forever()) if settings.ENGINE_ENABLED else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Secure Horizons (T0 shim)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(response_api.router, prefix="/api")
app.include_router(incidents_api.router, prefix="/api")
app.include_router(agent_api.router, prefix="/api")
_REPLAY_LOCK = threading.Lock()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "network": settings.NETWORK, "chain_id": settings.CHAIN_ID,
            "dry_run": settings.DRY_RUN_ACTIONS, "use_fixtures": settings.USE_FIXTURES, "shim": True}


@app.post("/api/demo/replay")
def demo_replay() -> dict:
    """SHIM-ONLY: replay R1 at block 45201812 into the store without a chain (dry-run only), then the reacted
    series up to 45201880 so the incident is contained. Idempotent: a second call changes nothing."""
    if not settings.DRY_RUN_ACTIONS:
        raise HTTPException(409, detail="replay runs in dry-run only (DRY_RUN_ACTIONS=true)")
    from backend import responder as responder_module
    from backend.tests.test_t5_factories import FORGED_BLOCK, make_alert_r1, make_reacted_series

    with _REPLAY_LOCK:
        if store.get_decision(f"DEC-fuji-{FORGED_BLOCK}-1") is None:
            known = {s.block_number for s in store.snapshots(limit=2000)}
            for snap in make_reacted_series():
                if snap.block_number in known:
                    continue
                if snap.block_number < FORGED_BLOCK:
                    store.add_snapshot(snap)
                elif snap.block_number == FORGED_BLOCK:
                    wall_clock = responder_module._now
                    responder_module._now = lambda: snap.block_time + timedelta(seconds=2)  # scenario clock
                    try:
                        engine.inject([make_alert_r1()], snap)
                    finally:
                        responder_module._now = wall_clock
                else:
                    store.add_snapshot(snap)
                    incidents.handle([], [], snap)
        latest = store.latest_snapshot()
        return {"decisions": [d.id for d in store.decisions()],
                "incidents": [{"id": i.id, "status": i.status, "saved_usd": i.saved_usd} for i in store.incidents()],
                "latest_block": latest.block_number if latest else None}
