# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T0 shim: backend/store.py (TASKS.md 2.10)."""
import json

import pytest

from backend import settings
from backend import store as store_mod
from backend.store import Store
from backend.tests.test_t4_fixtures import load_attack, make_alert
from backend.tests.test_t5_factories import make_alert_r1, make_decision_r1, run_reacted_incident


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    return Store()


def _runtime(tmp_path):
    return tmp_path / "runtime" / settings.NETWORK


def test_snapshots_add_and_read(tmp_store):
    assert tmp_store.latest_snapshot() is None
    s0, s1 = load_attack(45201800), load_attack(45201812)
    tmp_store.add_snapshot(s0)
    tmp_store.add_snapshot(s1)
    assert tmp_store.latest_snapshot().block_number == 45201812
    assert [s.block_number for s in tmp_store.snapshots()] == [45201800, 45201812]
    assert [s.block_number for s in tmp_store.snapshots(limit=1)] == [45201812]


def test_snapshot_cap(tmp_store, monkeypatch):
    monkeypatch.setattr(store_mod, "MAX_SNAPSHOTS", 3)
    for b in range(45201800, 45201810, 2):
        tmp_store.add_snapshot(load_attack(b))
    assert [s.block_number for s in tmp_store.snapshots()] == [45201804, 45201806, 45201808]


def test_alerts_since_block(tmp_store):
    a0 = make_alert("R2_LIQUIDITY_DROP", "high", load_attack(45201800), "lend-eth", "WETH", 1.0)
    a1 = make_alert_r1()
    tmp_store.add_alerts([a0, a1])
    assert [a.id for a in tmp_store.alerts()] == [a1.id, a0.id]  # newest first
    assert [a.id for a in tmp_store.alerts(since_block=45201812)] == [a1.id]


def test_decisions_update_and_get(tmp_store):
    d = make_decision_r1()
    tmp_store.add_decision(d)
    assert tmp_store.get_decision(d.id) == d
    assert tmp_store.get_decision("nope") is None
    changed = d.model_copy(update={"rationale": "changed"})
    tmp_store.update_decision(changed)
    assert len(tmp_store.decisions()) == 1
    assert tmp_store.get_decision(d.id).rationale == "changed"


def test_upsert_incident(tmp_store, monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    tmp_store.upsert_incident(incident)
    tmp_store.upsert_incident(incident.model_copy(update={"title": "renamed"}))
    assert [i.id for i in tmp_store.incidents()] == [incident.id]
    assert tmp_store.get_incident(incident.id).title == "renamed"
    assert tmp_store.get_incident("nope") is None


def test_jsonl_written_and_reset(tmp_store, tmp_path):
    tmp_store.add_snapshot(load_attack(45201812))
    tmp_store.add_alerts([make_alert_r1()])
    tmp_store.add_decision(make_decision_r1())
    runtime = _runtime(tmp_path)
    for name in ("snapshots", "alerts", "decisions"):
        lines = (runtime / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        json.loads(lines[0])

    assert tmp_store.generation == 0
    tmp_store.reset()
    assert tmp_store.generation == 1
    assert tmp_store.snapshots() == [] and tmp_store.alerts() == [] and tmp_store.decisions() == []
    assert tmp_store.incidents() == [] and tmp_store.latest_snapshot() is None
    assert not (runtime / "snapshots.jsonl").exists()
    assert len(list(runtime.glob("snapshots.*.jsonl"))) == 1
