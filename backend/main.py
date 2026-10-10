"""FastAPI entry point (TASKS.md 2.9 and 2.10). Owner: T0.

Run from the repo root: make backend   (uvicorn backend.main:app --port 8000, one worker: the store is in memory)

Each component comes from its owning task's module when that module exists, otherwise from a T0 fallback
(backend/_stubs.py, backend/api/_fixtures.py). Adding a module is enough to activate it: never edit this file
to plug in your task. If your module exists but fails to import, the error is raised, never hidden.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import _stubs, settings
from backend.api import _fixtures
from backend.store import store

log = logging.getLogger("uvicorn.error")  # shown by uvicorn at startup
SOURCES: dict[str, str] = {}  # component -> "real" or "fallback", logged at startup


def _load(module: str, attr: str, fallback: Any, component: str) -> Any:
    try:
        value = getattr(importlib.import_module(module), attr)
        SOURCES[component] = "real"
        return value
    except ModuleNotFoundError as exc:
        if exc.name != module:  # the module exists but one of its own imports is missing: surface it
            raise
        SOURCES[component] = "fallback"
        return fallback


Engine = _load("backend.engine", "Engine", _stubs.Engine, "engine (T3)")
Responder = _load("backend.responder", "Responder", _stubs.Responder, "responder (T4)")
get_executor = _load("backend.executor", "get_executor", _stubs.get_executor, "executor (T4)")
IncidentManager = _load("backend.incidents", "IncidentManager", _stubs.IncidentManager, "incidents (T5)")

engine = Engine(store)
responder = Responder(store, get_executor())
incidents = IncidentManager(store)
engine.on_alerts(responder.handle)
responder.on_decisions(incidents.handle)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for component, source in sorted(SOURCES.items()):
        log.info("component %-28s %s", component, source)
    task = asyncio.create_task(engine.run_forever()) if settings.ENGINE_ENABLED else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Secure Horizons treasury monitor", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for name, fallback, owner in (
    ("state", _fixtures.state, "T3"),
    ("response", _fixtures.response, "T4"),
    ("incidents", _fixtures.incidents, "T5"),
    ("demo", _fixtures.demo, "T2"),
    ("metrics", _fixtures.metrics, "T7"),
):
    router = _load(f"backend.api.{name}", "router", fallback, f"api/{name} ({owner})")
    app.include_router(router, prefix="/api")
