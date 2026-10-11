import asyncio
import threading
from datetime import timedelta

import httpx

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import engine, fixtures, settings
from backend.api import state
from backend.models import Health, SeriesPoint, StateResponse
from backend.store import Store
from backend.tests.test_t3_rules import load_series


@pytest.fixture
def api(monkeypatch, tmp_path):
    store = Store(runtime_dir=tmp_path)
    monkeypatch.setattr(state, "store", store)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    monkeypatch.setattr(engine, "STATUS", engine.EngineStatus())
    monkeypatch.setattr(state, "utcnow", lambda: load_series("snapshots_attack.jsonl")[-1].block_time)
    app = FastAPI()
    app.include_router(state.router, prefix="/api")
    with TestClient(app) as client:
        yield client, store


def test_invalid_timestamp_reports_degraded_instead_of_crashing(api):
    client, store = api
    s = load_series("snapshots_normal.jsonl")[0]
    s.source = "live"
    s.block_time = s.block_time.replace(tzinfo=None)
    store.add_snapshot(s)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert client.get("/api/state").status_code == 503


def test_invalid_series_snapshot_returns_service_unavailable(api):
    client, store = api
    s = load_series("snapshots_normal.jsonl")[0]
    s.positions[0].supplied = "invalid"
    store.add_snapshot(s)
    assert client.get("/api/series").status_code == 503


def test_empty_store(api):
    client, _ = api
    assert client.get("/api/state").status_code == 503
    assert client.get("/api/state").json() == {"detail": "no snapshot yet"}
    assert client.get("/api/alerts").json() == []
    assert client.get("/api/series").json() == []
    assert client.get("/api/health").json()["status"] == "degraded"


def test_fixture_mode_read_at_request_time(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    assert client.get("/api/state").json() == fixtures.load("state.json")
    assert client.get("/api/health").json() == fixtures.load("health.json")
    assert len(client.get("/api/series?limit=5").json()) == 5
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    assert client.get("/api/state").status_code == 503


def test_attack_engine_store_and_api(api):
    client, store = api
    monitor = engine.Engine(store)
    snapshots = load_series("snapshots_attack.jsonl")
    for s in snapshots:
        monitor.process(s)
    response = client.get("/api/state")
    value = StateResponse.model_validate(response.json())
    assert value.block_number == 45201880
    assert value.totals == {"value_usd": 1325000.0, "withdrawable_usd": 950000.0, "idle_usd": 0.0, "at_risk_usd": 375000.0}
    assert value.risk_level == "critical"
    alerts = client.get("/api/alerts").json()
    assert len(alerts) == 8
    assert alerts[0]["block_number"] == 45201878
    assert alerts[-1]["block_number"] == 45201812
    assert len(client.get("/api/alerts?since_block=45201836").json()) == 4
    points = client.get("/api/series?deployment_id=lend-eth&asset=WETH").json()
    assert len(points) == 41
    assert points[0]["available_liquidity"] == str(800 * 10**18)
    assert points[-1]["withdrawable_ratio_bps"] == 0
    assert points[-1]["backing_ratio_bps"] == 1935
    assert len(client.get("/api/series?limit=5").json()) == 5
    assert client.get("/api/series?asset=DAI").json() == []


def test_normal_run(api):
    client, store = api
    monitor = engine.Engine(store)
    for s in load_series("snapshots_normal.jsonl"):
        monitor.process(s)
    value = client.get("/api/state").json()
    assert value["risk_level"] == "info"
    assert value["totals"]["at_risk_usd"] == 0
    assert client.get("/api/alerts").json() == []


def test_idle_does_not_count_as_exposed_loss(api):
    _, store = api
    s = load_series("snapshots_attack.jsonl")[-1]
    s.vault.idle_balances["WETH"] = str(10 * 10**18)
    totals = state.compute_totals(s)
    assert totals["value_usd"] == 1_350_000
    assert totals["idle_usd"] == 25_000
    assert totals["at_risk_usd"] == 375_000


def test_state_does_not_advertise_paused_position_as_withdrawable(api):
    client, store = api
    s = load_series("snapshots_normal.jsonl")[0]
    next(r for r in s.reserves if (r.deployment_id, r.asset) == ("lend-eth", "WETH")).paused = True
    store.add_snapshot(s)
    value = client.get("/api/state").json()
    p = next(p for p in value["positions"] if (p["deployment_id"], p["asset"]) == ("lend-eth", "WETH"))
    assert p["withdrawable_usd"] == 0
    assert p["withdrawable_now"] == "0"
    assert value["totals"]["at_risk_usd"] == 375_000
    assert next(p for p in s.positions if (p.deployment_id, p.asset) == ("lend-eth", "WETH")).withdrawable_usd == 375_000


def test_real_data_coverage_is_not_hidden_by_healthy_rpc(api, monkeypatch):
    client, store = api
    snaps = load_series("snapshots_normal.jsonl")[:3]
    for s in snaps:
        s.source = "live"
        store.add_snapshot(s)
    monkeypatch.setattr(state, "utcnow", lambda: snaps[-1].block_time)
    engine.STATUS.running = engine.STATUS.rpc_ok = True
    health = client.get("/api/health")
    assert Health.model_validate(health.json()).status == "degraded"
    assert "canonical" in health.headers["X-Monitoring-Issues"].lower()
    response = client.get("/api/state")
    assert response.json()["risk_level"] == "warning"
    assert response.headers["X-Monitoring-Status"] == "degraded"


def test_stale_data_is_degraded_even_with_ok_rpc(api, monkeypatch):
    client, store = api
    s = load_series("snapshots_normal.jsonl")[0]
    s.source = "live"
    store.add_snapshot(s)
    monkeypatch.setattr(state, "utcnow", lambda: s.block_time + timedelta(hours=1))
    engine.STATUS.running = engine.STATUS.rpc_ok = True
    assert "stale" in client.get("/api/health").headers["X-Monitoring-Issues"].lower()
    assert client.get("/api/state").json()["risk_level"] != "info"


def test_no_snapshot_is_not_healthy_when_engine_flags_are_old(api):
    client, _ = api
    engine.STATUS.running = engine.STATUS.rpc_ok = True
    assert client.get("/api/health").json()["status"] == "degraded"


def test_maintenance_history_does_not_leak_into_risk_window(api, monkeypatch):
    client, store = api
    monitor = engine.Engine(store)
    maintenance = [True]
    monkeypatch.setattr(monitor, "in_maintenance", lambda: maintenance[0])
    start = load_series("snapshots_normal.jsonl")[0]
    start.reserves[1].available_liquidity = str(2000 * 10**18)
    monitor.process(start)
    maintenance[0] = False
    next_sample = load_series("snapshots_normal.jsonl")[1]
    monitor.process(next_sample)
    assert not any(a.rule_id == "R3_LIQUIDITY_DRAIN" for a in state.current_evaluation(store).alerts)
    assert client.get("/api/state").status_code == 200


def test_risk_recomputed_after_recovery_not_from_historical_alerts(api):
    client, store = api
    monitor = engine.Engine(store)
    for s in load_series("snapshots_attack.jsonl"):
        monitor.process(s)
    start = load_series("snapshots_normal.jsonl")[0]
    for i in range(20):
        monitor.process(start.model_copy(update={"block_number": 45201882 + i * 2,
                                                "block_time": start.block_time + timedelta(seconds=200 + i * 4)}))
    assert client.get("/api/state").json()["risk_level"] == "info"
    assert len(client.get("/api/alerts").json()) == 8


@pytest.mark.parametrize("query", ["/series?limit=0", "/series?limit=2001", "/series?limit=no", "/alerts?since_block=-1"])
def test_invalid_parameters(api, query):
    client, _ = api
    assert client.get("/api" + query).status_code == 422


def test_active_incident_id_and_schema(api):
    client, store = api
    from backend.models import Incident
    store.add_snapshot(load_series("snapshots_normal.jsonl")[0])
    incident = Incident.model_validate(fixtures.load("incident.json"))
    store.upsert_incident(incident)
    result = StateResponse.model_validate(client.get("/api/state").json())
    assert result.open_incident_id == incident.id
    for p in client.get("/api/series").json():
        SeriesPoint.model_validate(p)


def test_full_t3_collector_engine_store_api_path(api, monkeypatch):
    from backend import collector
    from backend.tests.test_t3_collector import FakeChain

    client, store = api
    snapshots = load_series("snapshots_attack.jsonl")
    rpc = FakeChain(snapshots[0])
    rpc.install(monkeypatch)
    monitor = engine.Engine(store, clock=lambda: rpc.snapshot.block_time)
    observed = []
    monitor.on_alerts(lambda alerts, snapshot: observed.extend(alerts))
    for raw in snapshots:
        rpc.snapshot = raw.model_copy(deep=True)
        rpc.block_number = raw.block_number
        monitor.process(collector.build_snapshot(raw.block_number, rpc))
    monkeypatch.setattr(state, "utcnow", lambda: rpc.snapshot.block_time)
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.json()["totals"]["at_risk_usd"] == 375_000
    assert response.json()["risk_level"] == "critical"
    assert len(client.get("/api/alerts").json()) == len(observed) == 8
    r1 = next(a for a in observed if a.rule_id == "R1_BRIDGE_INVARIANT")
    assert r1.severity == "critical"
    assert r1.metrics["evidence_status"] == "unverified"
    assert "canonical" in response.headers["X-Monitoring-Issues"].lower()


def test_full_t3_normal_collection_has_no_alerts(api, monkeypatch):
    from backend import collector
    from backend.tests.test_t3_collector import FakeChain

    client, store = api
    snapshots = load_series("snapshots_normal.jsonl")
    rpc = FakeChain(snapshots[0])
    rpc.install(monkeypatch)
    monitor = engine.Engine(store, clock=lambda: rpc.snapshot.block_time)
    for raw in snapshots:
        rpc.snapshot, rpc.block_number = raw, raw.block_number
        assert monitor.process(collector.build_snapshot(raw.block_number, rpc)) == []
    monkeypatch.setattr(state, "utcnow", lambda: rpc.snapshot.block_time)
    assert client.get("/api/alerts").json() == []
    assert client.get("/api/state").json()["totals"]["at_risk_usd"] == 0
    assert client.get("/api/health").json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_monitor_loop_keeps_real_api_responsive_during_slow_response(api, monkeypatch):
    from backend.tests.test_t3_collector import FakeChain

    client, store = api
    snapshots = load_series("snapshots_attack.jsonl")[:8]
    rpc = FakeChain(snapshots[0])
    rpc.install(monkeypatch)
    monitor = engine.Engine(store, clock=lambda: rpc.snapshot.block_time)
    monkeypatch.setattr(monitor, "_make_client", lambda url: rpc)
    monkeypatch.setattr(settings, "POLL_INTERVAL_S", 0.001)
    monkeypatch.setattr(state, "utcnow", lambda: rpc.snapshot.block_time)
    index = [0]
    entered, release = threading.Event(), threading.Event()

    def head(client):
        rpc.snapshot = snapshots[index[0]]
        rpc.block_number = rpc.snapshot.block_number
        index[0] = min(index[0] + 1, len(snapshots) - 1)
        return rpc.block_number

    def slow(alerts, snapshot):
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("Handler was not released")

    monkeypatch.setattr(monitor, "_head", head)
    monitor.on_alerts(slow)
    task = asyncio.create_task(monitor.run_forever())
    try:
        async with asyncio.timeout(3):
            while not entered.is_set() or store.latest_snapshot().block_number < snapshots[-1].block_number:
                await asyncio.sleep(0.001)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="http://test") as http:
            response = await asyncio.wait_for(http.get("/api/health"), timeout=0.5)
            assert response.status_code == 200
            assert response.json()["engine_running"] is True
            assert response.json()["block_number"] == snapshots[-1].block_number
            assert response.json()["status"] == "degraded"
    finally:
        release.set()
        monitor.stop()
        await asyncio.wait_for(task, timeout=3)


def test_new_router_is_loaded_by_existing_main(monkeypatch):
    from backend.main import app
    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    monkeypatch.setattr(settings, "ENGINE_ENABLED", False)
    assert len(state.router.routes) == 4
    with TestClient(app) as client:
        for path in ("/api/health", "/api/state", "/api/series", "/api/alerts"):
            assert "get" in app.openapi()["paths"][path]
            assert client.get(path).status_code == 200
