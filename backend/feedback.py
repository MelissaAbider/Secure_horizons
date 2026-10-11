"""Append-only, hash-chained alert feedback ledger for long-term human-in-the-loop ML.

The ledger records two immutable event types:
- observation: an alert as emitted, its layer/model versions, metrics and sanitized snapshot context;
- review: a human classification of that observation. Reviews are revisions, never in-place updates.

It deliberately does NOT retrain, replace or tune the active model. `export_training_rows` only builds a reviewed dataset
for an offline challenger. Promotion remains a separate, explicit human-controlled process.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend import settings
from backend.agent_monitor import _compact
from backend.models import Alert, Snapshot

FeedbackLabel = Literal["confirmed_attack", "legitimate_activity", "insufficient_evidence", "duplicate", "wrong_scope", "uncertain"]
ReasonCode = Literal["bridge_mismatch", "collateral_surge", "liquidity_drain", "exitability_loss", "containment", "planned_activity",
                     "market_volatility", "stale_or_missing_data", "duplicate_signal", "scope_error", "other"]


class FeedbackRequest(BaseModel):
    label: FeedbackLabel
    reviewer: str = Field(min_length=2, max_length=80)
    reason_code: ReasonCode
    note: str = Field(default="", max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @field_validator("reviewer")
    @classmethod
    def reviewer_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reviewer cannot be blank")
        return value


class LedgerEvent(BaseModel):
    sequence: int
    event_id: str
    event_type: Literal["observation", "review"]
    at: datetime
    alert_id: str
    payload: dict
    previous_hash: str
    record_hash: str


class AlertFeedbackView(BaseModel):
    alert_id: str
    observation: dict | None = None
    reviews: list[dict] = Field(default_factory=list)
    current_review: dict | None = None
    chain_valid: bool = True


ZERO_HASH = "0" * 64


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _event_hash(unsigned: dict) -> str:
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _layer(rule_id: str) -> str:
    if rule_id.startswith("R6_"):
        return "ml"
    if rule_id.startswith("R7_"):
        return "llm"
    return "rules"


class FeedbackLedger:
    def __init__(self, runtime_dir: Path | None = None, clock=None):
        self.runtime_dir = runtime_dir
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

    def _path(self) -> Path:
        folder = self.runtime_dir or settings.runtime_dir()
        return folder / "alert_feedback.jsonl"

    def _read(self) -> list[LedgerEvent]:
        path = self._path()
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(LedgerEvent.model_validate_json(line))
        return events

    def verify(self) -> tuple[bool, list[str]]:
        with self._lock:
            errors, previous = [], ZERO_HASH
            for index, event in enumerate(self._read(), start=1):
                unsigned = event.model_dump(mode="json", exclude={"record_hash"})
                expected = _event_hash(unsigned)
                if event.sequence != index:
                    errors.append(f"sequence {event.sequence} expected {index}")
                if event.previous_hash != previous:
                    errors.append(f"event {event.event_id}: previous hash mismatch")
                if event.record_hash != expected:
                    errors.append(f"event {event.event_id}: record hash mismatch")
                previous = event.record_hash
            return not errors, errors

    def _append(self, event_type: str, alert_id: str, payload: dict, event_id: str | None = None) -> LedgerEvent:
        with self._lock:
            events = self._read()
            if event_id:
                existing = next((e for e in events if e.event_id == event_id), None)
                if existing:
                    return existing
            unsigned = {"sequence": len(events) + 1, "event_id": event_id or str(uuid.uuid4()), "event_type": event_type,
                        "at": self.clock(), "alert_id": alert_id, "payload": payload,
                        "previous_hash": events[-1].record_hash if events else ZERO_HASH}
            draft = LedgerEvent(**unsigned, record_hash=ZERO_HASH)
            normalized = draft.model_dump(mode="json", exclude={"record_hash"})
            event = draft.model_copy(update={"record_hash": _event_hash(normalized)})
            path = self._path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return event

    def observe(self, alert: Alert, snapshot: Snapshot) -> LedgerEvent:
        payload = {"layer": _layer(alert.rule_id), "rule_id": alert.rule_id, "severity": alert.severity,
                   "network": alert.network, "block_number": alert.block_number, "deployment_id": alert.deployment_id,
                   "asset": alert.asset, "title": alert.title, "explanation": alert.explanation,
                   "metrics": alert.metrics, "exposure_usd": alert.exposure_usd, "version": alert.rules_version,
                   "snapshot_hash": hashlib.sha256(_canonical(_compact(snapshot))).hexdigest(), "context": _compact(snapshot)}
        return self._append("observation", alert.id, payload, event_id=f"OBS-{alert.id}")

    def review(self, alert_id: str, request: FeedbackRequest) -> LedgerEvent:
        with self._lock:
            events = self._read()
            if not any(e.event_type == "observation" and e.alert_id == alert_id for e in events):
                raise KeyError(alert_id)
            event_id = f"REV-{alert_id}-{request.request_id}" if request.request_id else None
            return self._append("review", alert_id, request.model_dump(exclude_none=True), event_id=event_id)

    def views(self, alert_id: str | None = None) -> list[AlertFeedbackView]:
        with self._lock:
            events = self._read()
            valid, _ = self.verify()
            grouped: dict[str, AlertFeedbackView] = {}
            for event in events:
                if alert_id and event.alert_id != alert_id:
                    continue
                view = grouped.setdefault(event.alert_id, AlertFeedbackView(alert_id=event.alert_id, chain_valid=valid))
                item = {"event_id": event.event_id, "at": event.at.isoformat(), **event.payload, "record_hash": event.record_hash}
                if event.event_type == "observation":
                    view.observation = item
                else:
                    view.reviews.append(item)
                    view.current_review = item
            return list(reversed(grouped.values()))

    def export_training_rows(self) -> list[dict]:
        rows = []
        for view in self.views():
            if view.observation is None or view.current_review is None:
                continue
            rows.append({"alert_id": view.alert_id, "label": view.current_review["label"],
                         "reason_code": view.current_review["reason_code"], "reviewer": view.current_review["reviewer"],
                         "reviewed_at": view.current_review["at"], "layer": view.observation["layer"],
                         "rule_id": view.observation["rule_id"], "severity": view.observation["severity"],
                         "version": view.observation["version"], "metrics": view.observation["metrics"],
                         "snapshot_hash": view.observation["snapshot_hash"], "context": view.observation["context"],
                         "observation_hash": view.observation["record_hash"], "review_hash": view.current_review["record_hash"]})
        return rows

    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> None:
        for alert in alerts:
            try:
                self.observe(alert, snapshot)
            except Exception:
                # Audit failure must not stop detection or response. Health is exposed through /feedback/integrity.
                pass


feedback_ledger = FeedbackLedger()
