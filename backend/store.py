# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""Shared in-memory store with JSONL append (TASKS.md 2.10).

Ordering follows what T4/T5 rely on (their FakeStore): alerts() and decisions() newest first, incidents() in
insertion order (upsert replaces in place), snapshots(limit) chronological last `limit`.
settings.DATA_DIR and settings.NETWORK are read at call time so tests can monkeypatch them.
No reload from disk at start: the JSONL files are an append-only journal.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from backend import settings
from backend.models import Alert, Decision, Incident, Snapshot

MAX_SNAPSHOTS = 2000
FILES = ("snapshots", "alerts", "decisions", "incidents")


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.generation: int = 0
        self._clear()

    def _clear(self) -> None:
        self._snapshots: list[Snapshot] = []
        self._alerts: list[Alert] = []
        self._decisions: list[Decision] = []
        self._incidents: list[Incident] = []

    # ---------- journal ----------

    @staticmethod
    def _dir() -> Path:
        return settings.DATA_DIR / "runtime" / settings.NETWORK

    def _append(self, name: str, models: list[BaseModel]) -> None:
        if not models:
            return
        path = self._dir() / f"{name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for m in models:
                f.write(m.model_dump_json() + "\n")

    # ---------- snapshots ----------

    def add_snapshot(self, s: Snapshot) -> None:
        with self._lock:
            self._snapshots.append(s)
            if len(self._snapshots) > MAX_SNAPSHOTS:
                del self._snapshots[:len(self._snapshots) - MAX_SNAPSHOTS]
            self._append("snapshots", [s])

    def latest_snapshot(self) -> Snapshot | None:
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def snapshots(self, limit: int = 500) -> list[Snapshot]:
        with self._lock:
            return list(self._snapshots[-limit:]) if limit > 0 else []

    # ---------- alerts ----------

    def add_alerts(self, alerts: list[Alert]) -> None:
        with self._lock:
            self._alerts.extend(alerts)
            self._append("alerts", list(alerts))

    def alerts(self, since_block: int = 0) -> list[Alert]:
        with self._lock:
            return [a for a in reversed(self._alerts) if a.block_number >= since_block]

    # ---------- decisions ----------

    def add_decision(self, d: Decision) -> None:
        with self._lock:
            self._decisions.append(d)
            self._append("decisions", [d])

    def update_decision(self, d: Decision) -> None:
        with self._lock:
            self._decisions = [d if x.id == d.id else x for x in self._decisions]
            self._append("decisions", [d])

    def decisions(self) -> list[Decision]:
        with self._lock:
            return list(reversed(self._decisions))

    def get_decision(self, decision_id: str) -> Decision | None:
        with self._lock:
            return next((d for d in self._decisions if d.id == decision_id), None)

    # ---------- incidents ----------

    def upsert_incident(self, i: Incident) -> None:
        with self._lock:
            for k, x in enumerate(self._incidents):
                if x.id == i.id:
                    self._incidents[k] = i
                    break
            else:
                self._incidents.append(i)
            self._append("incidents", [i])

    def incidents(self) -> list[Incident]:
        with self._lock:
            return list(self._incidents)

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._lock:
            return next((i for i in self._incidents if i.id == incident_id), None)

    # ---------- reset ----------

    def reset(self) -> None:
        """Clears memory, renames the JSONL files with a UTC timestamp suffix, increments generation."""
        with self._lock:
            self._clear()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            directory = self._dir()
            for name in FILES:
                path = directory / f"{name}.jsonl"
                if path.exists():
                    path.rename(directory / f"{name}.{stamp}.jsonl")
            self.generation += 1


store = Store()
