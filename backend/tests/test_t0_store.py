"""T0-06: shared store."""
from __future__ import annotations

from pathlib import Path

from backend import fixtures
from backend.models import Alert, Decision, Incident, Snapshot
from backend.store import Store


def test_store_roundtrip(tmp_path: Path) -> None:
    s = Store(runtime_dir=tmp_path)
    snaps = [Snapshot.model_validate(r) for r in fixtures.load_jsonl("snapshots_attack.jsonl")[:3]]
    for snap in snaps:
        s.add_snapshot(snap)
    assert s.latest_snapshot() == snaps[-1] and len(s.snapshots(limit=2)) == 2
    alert = Alert.model_validate(fixtures.load("alerts.json")[0])
    s.add_alerts([alert])
    assert s.alerts(since_block=alert.block_number) == [alert] and s.alerts(since_block=alert.block_number + 1) == []
    decision = Decision.model_validate(fixtures.load("decisions.json")[0])
    s.add_decision(decision)
    decision.actions[7].status = "approved"
    s.update_decision(decision)
    assert s.get_decision(decision.id).actions[7].status == "approved" and len(s.decisions()) == 1
    incident = Incident.model_validate(fixtures.load("incident.json"))
    s.upsert_incident(incident)
    assert s.get_incident(incident.id) == incident
    assert (tmp_path / "snapshots.jsonl").read_text().count("\n") == 3
    generation = s.generation
    s.reset()
    assert s.generation == generation + 1
    assert s.latest_snapshot() is None and s.alerts() == [] and s.decisions() == [] and s.incidents() == []
    assert not (tmp_path / "snapshots.jsonl").exists()
