"""FastAPI entry point (TASKS.md 2.9, 2.10). Owner: T0. Run: make backend (one worker: the store is in memory).

Mounts the router of each task and wires engine -> responder -> incidents, for the modules that exist.
A task plugs in by adding its own file; nobody edits this one. A missing module is skipped; a module that
exists but fails to import raises.
"""
from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager
from types import ModuleType
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import settings
from backend.store import store


def _optional(module: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise
        return None


_engine, _responder, _executor, _incidents = (_optional(f"backend.{m}") for m in ("engine", "responder", "executor", "incidents"))
engine = _engine.Engine(store) if _engine else None
responder = _responder.Responder(store, _executor.get_executor()) if _responder and _executor else None
incidents = _incidents.IncidentManager(store) if _incidents else None
if engine and responder:
    engine.on_alerts(responder.handle)
if responder and incidents:
    responder.on_decisions(incidents.handle)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(engine.run_forever()) if engine and settings.ENGINE_ENABLED else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Secure Horizons treasury monitor", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for name in ("state", "response", "incidents", "demo", "metrics"):  # owners: T3, T4, T5, T2, T7
    router_module = _optional(f"backend.api.{name}")
    if router_module:
        app.include_router(router_module.router, prefix="/api")
