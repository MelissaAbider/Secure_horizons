"""T5-27: third-party register statuses (TASKS.md T5 8)."""
from datetime import timedelta

from backend import llm
from backend.incidents import dependency_statuses
from backend.models import Dependency
from backend.tests.test_t5_factories import FakeStore, load_attack


def test_statuses():
    llm.reset()
    store = FakeStore()
    series = load_attack()
    for s in series:
        store.add_snapshot(s)
    latest = series[40]
    deps = dependency_statuses(store, now=latest.block_time + timedelta(seconds=10))
    assert len(deps) == 9
    assert all(isinstance(d, Dependency) for d in deps)
    status = {d.id: d.status for d in deps}
    assert status["rseth"] == "down"
    assert status["lend-eth"] == "degraded"
    assert status["lend-avax"] == "ok"
    assert status["rpc-fuji"] == "ok"
    assert status["aws-sns"] == "unknown"
    assert status["bedrock"] == "unknown"
    assert status["oracle"] == "ok"
    assert [d.id for d in deps][:2] == ["rpc-fuji", "aws-compute"]  # YAML order
    later = {d.id: d.status for d in dependency_statuses(store, now=latest.block_time + timedelta(seconds=200))}
    assert later["rpc-fuji"] == "down"
    assert {d.id: d.status for d in dependency_statuses(FakeStore())}["rpc-fuji"] == "unknown"
