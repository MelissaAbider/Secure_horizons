# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""FastAPI app: T4 + T5 routes under /api, wired to the stub engine (TASKS.md 2.9, 2.11).

Run with a single uvicorn worker only: the store, the executor and the wiring are in-process singletons.
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import settings
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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "network": settings.NETWORK, "chain_id": settings.CHAIN_ID,
            "dry_run": settings.DRY_RUN_ACTIONS, "use_fixtures": settings.USE_FIXTURES, "shim": True}
