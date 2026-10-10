"""Fallback no-op components (TASKS.md 2.10). Owner: T0.

backend/main.py uses a class from here ONLY while the real module of the owning task does not exist yet
(backend/engine.py for T3, backend/responder.py and backend/executor.py for T4, backend/incidents.py for T5).
As soon as a task adds its file, main.py picks it up: no file ever has two authors. No business logic here.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Callable, Optional

from backend import settings
from backend.models import Action, Alert, Decision, Incident, Snapshot

log = logging.getLogger("backend.stubs")


class Engine:
    """Stand-in for T3: stores snapshots it is given, raises no alert, reads nothing from the chain."""

    def __init__(self, store) -> None:
        self.store = store
        self.handlers: list[Callable[[list[Alert], Snapshot], Any]] = []
        self.running = False

    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], Any]) -> None:
        self.handlers.append(handler)

    def process(self, snapshot: Snapshot) -> list[Alert]:
        self.store.add_snapshot(snapshot)
        return []

    async def run_forever(self) -> None:
        self.running = True
        log.warning("engine stub running: no chain reads until backend/engine.py (T3) exists")
        while True:
            await asyncio.sleep(settings.POLL_INTERVAL_S)


def plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]:
    return []


class Responder:
    """Stand-in for T4: takes no decision."""

    def __init__(self, store, executor) -> None:
        self.store = store
        self.executor = executor
        self.handlers: list[Callable[[list[Decision], list[Alert], Snapshot], Any]] = []

    def on_decisions(self, handler: Callable[[list[Decision], list[Alert], Snapshot], Any]) -> None:
        self.handlers.append(handler)

    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> list[Decision]:
        return []


class IncidentManager:
    """Stand-in for T5: opens no incident."""

    def __init__(self, store) -> None:
        self.store = store

    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Optional[Incident]:
        return None


class DryRunExecutor:
    """Stand-in for T4's executor: sends nothing, returns deterministic fake hashes starting with 0xdry."""

    @staticmethod
    def _result(kind: str, **params: Any) -> dict[str, Any]:
        digest = hashlib.sha256(json.dumps({"kind": kind, **params}, sort_keys=True).encode()).hexdigest()
        return {"tx_hash": "0xdry" + digest[:59], "status": 1, "block_number": None, "note": "stub dry run"}

    def pause_deposits(self) -> dict[str, Any]:
        return self._result("pause_deposits")

    def unpause_deposits(self) -> dict[str, Any]:
        return self._result("unpause_deposits")

    def emergency_withdraw(self, deployment_id: str, asset: str) -> dict[str, Any]:
        return self._result("emergency_withdraw", deployment_id=deployment_id, asset=asset)

    def anchor(self, record_hash: str, kind: str, uri: str) -> dict[str, Any]:
        return self._result("anchor", record_hash=record_hash, kind=kind, uri=uri)


_executor: Optional[DryRunExecutor] = None


def get_executor() -> DryRunExecutor:
    global _executor
    if _executor is None:
        _executor = DryRunExecutor()
    return _executor
