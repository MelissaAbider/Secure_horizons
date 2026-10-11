import asyncio
import threading
from datetime import timedelta

import pytest

from backend import settings
from backend.engine import Engine, STATUS
from backend.tests.test_t3_hardening import advance, reserve, token
from backend.tests.test_t3_rules import MemStore, load_series


@pytest.fixture
def healthy():
    return load_series("snapshots_normal.jsonl")[0].model_copy(deep=True)


def test_maintenance_rechecks_same_block_and_clears_history(healthy, monkeypatch):
    engine = Engine(MemStore())
    token(healthy).bridge_destination_nonce += 1
    maintenance = [True]
    monkeypatch.setattr(engine, "in_maintenance", lambda: maintenance[0])
    assert not engine.process(healthy)
    assert not engine.window
    maintenance[0] = False
    assert engine.process(healthy)[0].rule_id == "R1_BRIDGE_INVARIANT"
    assert len(engine.window) == 1
    assert not engine.process(healthy)


def test_store_generation_and_chain_rewind_rearm(healthy):
    engine = Engine(MemStore())
    token(healthy).bridge_destination_nonce += 1
    assert engine.process(healthy)
    assert not engine.process(advance(healthy))
    engine.store.generation += 1
    assert engine.process(advance(healthy))
    assert len(engine.window) == 1
    assert engine.process(healthy)
    assert len(engine.window) == 1


def test_unknown_evidence_visible_without_claiming_recovery(healthy):
    engine = Engine(MemStore())
    token(healthy).bridge_destination_nonce += 1
    engine.process(healthy)
    unknown = advance(healthy)
    token(unknown).bridge_destination_nonce = None
    assert not engine.process(unknown)
    assert STATUS.data_issues
    assert engine.last_evaluation.unavailable_rules == {"R1_BRIDGE_INVARIANT"}
    assert engine.latch.active()


def test_handlers_cannot_mutate_shared_snapshot_or_alerts(healthy):
    engine = Engine(MemStore())
    token(healthy).bridge_destination_nonce += 1
    seen = []

    def mutate(alerts, snapshot):
        alerts[0].severity = "info"
        token(snapshot).bridge_destination_nonce = 0
        raise RuntimeError("handler failed")

    engine.on_alerts(mutate)
    engine.on_alerts(lambda alerts, snapshot: seen.append((alerts[0].severity, token(snapshot).bridge_destination_nonce)))
    result = engine.process(healthy)
    assert result[0].severity == "critical"
    assert seen == [("critical", 308)]
    assert engine.store.saved_alerts[0].severity == "critical"
    assert token(engine.window[-1]).bridge_destination_nonce == 308
    assert STATUS.handler_error == "RuntimeError"


def test_future_live_data_rejected(healthy):
    healthy.source = "live"
    engine = Engine(MemStore(), clock=lambda: healthy.block_time - timedelta(minutes=1))
    with pytest.raises(ValueError, match="future"):
        engine.process(healthy)
    assert engine._last_block is None


def test_invalid_data_cannot_consume_block_or_clear_latch(healthy):
    engine = Engine(MemStore())
    token(healthy).bridge_destination_nonce += 1
    engine.process(healthy)
    bad = advance(healthy)
    reserve(bad).total_borrowed = "nan"
    active = engine.latch.active()
    with pytest.raises(ValueError):
        engine.process(bad)
    assert engine.latch.active() == active
    assert engine._last_block == healthy.block_number
    assert not engine.process(advance(healthy))


def setup_loop(engine, healthy, monkeypatch):
    healthy.source = "live"
    monkeypatch.setattr(settings, "NETWORK", healthy.network)
    monkeypatch.setattr(settings, "CHAIN_ID", healthy.chain_id)
    monkeypatch.setattr(settings, "POLL_INTERVAL_S", 0.001)
    monkeypatch.setattr(settings, "RPC_URL", "primary")
    monkeypatch.setattr(settings, "RPC_FALLBACK_URL", "fallback")
    monkeypatch.setattr(engine, "_make_client", lambda url: url)
    monkeypatch.setattr(engine, "_deployment_key", lambda: (1, healthy.vault.address))


@pytest.mark.asyncio
async def test_slow_handlers_do_not_block_collection_and_remain_serial(healthy, monkeypatch):
    engine = Engine(MemStore(), clock=lambda: healthy.block_time + timedelta(seconds=20))
    setup_loop(engine, healthy, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    head = [healthy.block_number]
    completed = []
    active = [0]
    maximum = [0]

    def get_head(client):
        head[0] += 1
        return head[0]

    def collect(block, client):
        s = advance(healthy, block - healthy.block_number)
        reserve(s, "rsETH").frozen = True
        if block >= healthy.block_number + 2:
            reserve(s).paused = True
        return s

    def handler(alerts, snapshot):
        active[0] += 1
        maximum[0] = max(maximum[0], active[0])
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("Test handler was not released")
        completed.append(snapshot.block_number)
        active[0] -= 1

    monkeypatch.setattr(engine, "_head", get_head)
    monkeypatch.setattr(engine, "_build_snapshot", collect)
    engine.on_alerts(handler)
    task = asyncio.create_task(engine.run_forever())
    try:
        async with asyncio.timeout(3):
            while not entered.is_set() or len(engine.store.saved_snapshots) < 3:
                await asyncio.sleep(0.001)
            assert STATUS.running
            assert len(engine.store.saved_snapshots) >= 3
            assert not completed
            release.set()
            while len(completed) < 2:
                await asyncio.sleep(0.001)
        assert maximum == [1]
        assert completed[:2] == [healthy.block_number + 1, healthy.block_number + 2]
    finally:
        release.set()
        engine.stop()
        await asyncio.wait_for(task, timeout=3)
    assert not STATUS.running


@pytest.mark.asyncio
async def test_rpc_fallback_after_three_errors_without_logging_credentials(healthy, monkeypatch, caplog):
    engine = Engine(MemStore(), clock=lambda: healthy.block_time)
    setup_loop(engine, healthy, monkeypatch)
    calls = []

    def get_head(client):
        calls.append(client)
        if client == "primary":
            raise ConnectionError("https://user:secret@example.invalid/rpc?token=secret")
        return healthy.block_number

    def collect(block, client):
        engine.stop()
        return healthy

    monkeypatch.setattr(engine, "_head", get_head)
    monkeypatch.setattr(engine, "_build_snapshot", collect)
    await asyncio.wait_for(engine.run_forever(), timeout=3)
    assert calls == ["primary"] * 3 + ["fallback"]
    assert len(engine.store.saved_snapshots) == 1
    assert STATUS.rpc_url == "fallback"
    assert "secret" not in caplog.text
    assert not STATUS.running


@pytest.mark.asyncio
async def test_stopped_chain_becomes_stale(healthy, monkeypatch):
    now = [healthy.block_time]
    engine = Engine(MemStore(), clock=lambda: now[0])
    setup_loop(engine, healthy, monkeypatch)
    count = [0]

    def head(client):
        count[0] += 1
        if count[0] > 1:
            now[0] = healthy.block_time + timedelta(hours=1)
            engine.stop()
        return healthy.block_number

    monkeypatch.setattr(engine, "_head", head)
    monkeypatch.setattr(engine, "_build_snapshot", lambda block, client: healthy)
    await asyncio.wait_for(engine.run_forever(), timeout=3)
    assert len(engine.store.saved_snapshots) == 1
    assert STATUS.last_error == "ValueError"
    assert not STATUS.rpc_ok


@pytest.mark.asyncio
async def test_real_loop_rejects_fixture_evidence(healthy, monkeypatch):
    engine = Engine(MemStore(), clock=lambda: healthy.block_time)
    setup_loop(engine, healthy, monkeypatch)
    healthy.source = "fixture"
    monkeypatch.setattr(engine, "_head", lambda client: healthy.block_number)

    def collect(block, client):
        engine.stop()
        return healthy

    monkeypatch.setattr(engine, "_build_snapshot", collect)
    await engine.run_forever()
    assert not engine.store.saved_snapshots
    assert STATUS.last_error == "ValueError"


def test_conflicting_same_block_snapshot_is_not_silently_ignored(healthy):
    engine = Engine(MemStore())
    engine.process(healthy)
    changed = healthy.model_copy(deep=True)
    token(changed).bridge_destination_nonce += 1
    with pytest.raises(ValueError, match="same block"):
        engine.process(changed)


def test_store_failure_does_not_consume_an_alert(healthy):
    engine = Engine(MemStore())
    engine.process(healthy)
    broken = advance(healthy)
    token(broken).bridge_destination_nonce += 1
    original = engine.store.add_alerts

    def fail(alerts):
        raise OSError("disk full")

    engine.store.add_alerts = fail
    with pytest.raises(OSError):
        engine.process(broken)
    engine.store.add_alerts = original
    assert any(a.rule_id == "R1_BRIDGE_INVARIANT" for a in engine.process(broken))


@pytest.mark.asyncio
async def test_lagging_rpc_does_not_replay_old_blocks(healthy, monkeypatch):
    engine = Engine(MemStore(), clock=lambda: healthy.block_time)
    setup_loop(engine, healthy, monkeypatch)
    count = [0]

    def head(client):
        count[0] += 1
        if count[0] == 1:
            return healthy.block_number
        engine.stop()
        return healthy.block_number - 1

    monkeypatch.setattr(engine, "_head", head)
    monkeypatch.setattr(engine, "_build_snapshot", lambda block, client: healthy)
    await engine.run_forever()
    assert len(engine.store.saved_snapshots) == 1
    assert STATUS.last_error == "ValueError"


@pytest.mark.parametrize("problem", ["data_issues", "maintenance", "handler_error", "backpressure"])
def test_connectivity_does_not_imply_healthy_detection(problem):
    from backend.engine import EngineStatus
    status = EngineStatus(running=True, rpc_ok=True)
    assert status.detection_ok
    setattr(status, problem, ["unknown"] if problem == "data_issues" else "failure" if problem == "handler_error" else True)
    assert not status.detection_ok


def test_rpc_wrong_chain_is_rejected(healthy):
    from types import SimpleNamespace
    client = SimpleNamespace(eth=SimpleNamespace(chain_id=-1, block_number=1))
    with pytest.raises(ValueError, match="chain ID"):
        Engine(MemStore())._head(client)
