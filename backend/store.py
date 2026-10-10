"""Shared in-memory store (TASKS.md 2.10). Owner: T0.

Single instance `store`, imported by every task. Thread-safe. Every write is also appended as JSONL to
data/runtime/<network>/ so a session can be inspected after a crash. reset() empties everything and
increments `generation`: the engine (T3) clears its window when the generation changes.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend import settings
from backend.models import Alert, Decision, Incident, Snapshot

MAX_SNAPSHOTS = 2000


class Store:
    def __init__(self, runtime_dir: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._runtime_dir = runtime_dir
        self.generation = 0
        self._snapshots: list[Snapshot] = []
        self._alerts: list[Alert] = []
        self._decisions: dict[str, Decision] = {}
        self._incidents: dict[str, Incident] = {}

    # ---- persistence -------------------------------------------------------------------------
    def _dir(self) -> Path:
        return self._runtime_dir or settings.runtime_dir()

    def _append(self, name: str, item: BaseModel) -> None:
        path = self._dir() / f"{name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(item.model_dump_json() + "\n")

    # ---- snapshots ---------------------------------------------------------------------------
    def add_snapshot(self, s: Snapshot) -> None:
        with self._lock:
            self._snapshots.append(s)
            del self._snapshots[:-MAX_SNAPSHOTS]
            self._append("snapshots", s)

    def latest_snapshot(self) -> Optional[Snapshot]:
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def snapshots(self, limit: int = 500) -> list[Snapshot]:
        with self._lock:
            return list(self._snapshots[-limit:])

    # ---- alerts ------------------------------------------------------------------------------
    def add_alerts(self, alerts: list[Alert]) -> None:
        with self._lock:
            for a in alerts:
                self._alerts.append(a)
                self._append("alerts", a)

    def alerts(self, since_block: int = 0) -> list[Alert]:
        """Newest first."""
        with self._lock:
            return [a for a in reversed(self._alerts) if a.block_number >= since_block]

    # ---- decisions ---------------------------------------------------------------------------
    def add_decision(self, d: Decision) -> None:
        with self._lock:
            self._decisions[d.id] = d
            self._append("decisions", d)

    def update_decision(self, d: Decision) -> None:
        self.add_decision(d)

    def decisions(self) -> list[Decision]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._decisions.values()))

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        with self._lock:
            return self._decisions.get(decision_id)

    # ---- incidents ---------------------------------------------------------------------------
    def upsert_incident(self, i: Incident) -> None:
        with self._lock:
            self._incidents[i.id] = i
            self._append("incidents", i)

    def incidents(self) -> list[Incident]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._incidents.values()))

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._lock:
            return self._incidents.get(incident_id)

    # ---- reset -------------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._alerts.clear()
            self._decisions.clear()
            self._incidents.clear()
            self.generation += 1
            folder = self._dir()
            if folder.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                for path in folder.glob("*.jsonl"):
                    path.rename(path.with_name(f"{path.stem}.{stamp}.jsonl.bak"))


store = Store()
