# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T4 + T5 end-to-end through the T0 shim wiring (dry-run, offline).

Real Store, main.wire(): engine.inject(R1 alert at 45201812) -> Responder (T4) -> IncidentManager (T5),
then the T4/T5 routes through main.app.
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend import evidence, responder as responder_mod, settings
from backend.api import incidents as incidents_api
from backend.api import response as response_api
from backend.executor import get_executor
from backend.store import Store
from backend.tests.test_t4_fixtures import FORGED_BLOCK, load_attack
from backend.tests.test_t5_factories import make_alert_r1

DEC_ID = "DEC-fuji-45201812-1"
INC_ID = "INC-20261011-001"


@pytest.fixture
def shim_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", True)
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    for name in ("ALERT_WEBHOOK_URL", "SNS_TOPIC_ARN", "EVIDENCE_BUCKET", "BEDROCK_MODEL_ID"):
        monkeypatch.setattr(settings, name, "")
    get_executor.cache_clear()
    yield tmp_path
    get_executor.cache_clear()


@pytest.fixture
def scenario(shim_env, monkeypatch):
    import backend.main as main

    store = Store()
    engine, _responder, _incidents = main.wire(store)
    main.app.dependency_overrides[response_api.get_store] = lambda: store
    main.app.dependency_overrides[incidents_api.get_store] = lambda: store
    snap = load_attack(FORGED_BLOCK)
    monkeypatch.setattr(responder_mod, "_now", lambda: snap.block_time + timedelta(seconds=2))  # scenario clock
    alert = make_alert_r1()
    engine.inject([alert], snap)
    yield store, engine, alert, snap, TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_decision_from_engine(scenario):
    store, _, alert, _, _ = scenario
    (d,) = store.decisions()
    assert d.id == DEC_ID
    assert d.severity == "critical"
    assert d.exposure_usd == 1325000.0 and d.withdrawable_usd == 1325000.0
    assert d.matrix_cell == "critical|exposure>=1k|exit_possible"
    assert d.alert_ids == [alert.id]
    assert d.record_hash and d.anchor_tx.startswith("0xdry")
    assert [(a.type, a.params.get("deployment_id"), a.params.get("asset"), a.status) for a in d.actions] == [
        ("NOTIFY", None, None, "executed"),
        ("PAUSE_DEPOSITS", None, None, "executed"),
        ("EMERGENCY_WITHDRAW", "lend-eth", "USDC", "executed"),
        ("EMERGENCY_WITHDRAW", "lend-eth", "WETH", "executed"),
        ("EMERGENCY_WITHDRAW", "lend-avax", "USDC", "executed"),
        ("EMERGENCY_WITHDRAW", "lend-avax", "WETH", "executed"),
        ("OPEN_INCIDENT", None, None, "executed"),
        ("UNPAUSE_DEPOSITS", None, None, "pending_approval"),
    ]
    assert [a.amount for a in d.actions if a.type == "EMERGENCY_WITHDRAW"] == [
        "400000000000", "150000000000000000000", "300000000000", "100000000000000000000"]
    assert d.actions[0].note == "channels: log"


def test_incident_and_journal(scenario):
    store, _, alert, _, _ = scenario
    tmp = settings.DATA_DIR
    (inc,) = store.incidents()
    assert inc.id == INC_ID
    assert inc.status == "open" and inc.severity == "critical"
    assert inc.saved_usd == 1325000.0 and inc.exposure_usd == 1325000.0
    assert inc.decision_ids == [DEC_ID] and inc.alert_ids == [alert.id]
    assert inc.dora is not None
    assert (tmp / "evidence" / f"{DEC_ID}.json").exists()
    for name in ("snapshots", "alerts", "decisions", "incidents"):
        assert (tmp / "runtime" / settings.NETWORK / f"{name}.jsonl").exists(), name


def test_api_flow(scenario):
    store, _, _, _, client = scenario

    resp = client.get("/api/decisions")
    assert resp.status_code == 200 and [d["id"] for d in resp.json()] == [DEC_ID]

    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    assert [i["id"] for i in resp.json()] == [INC_ID] and resp.json()[0]["saved_usd"] == 1325000.0

    resp = client.get(f"/api/incidents/{INC_ID}/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text.startswith("# DORA initial notification (draft, human review required)")

    resp = client.post(f"/api/verify/{DEC_ID}")
    assert resp.status_code == 200 and resp.json()["match"] is True and resp.json()["anchored"] is True

    body = {"action_index": 7, "approver": "risk-officer", "approve": True}
    resp = client.post(f"/api/decisions/{DEC_ID}/approve", json=body)
    assert resp.status_code == 200, resp.text
    unpause = resp.json()["actions"][7]
    assert unpause["type"] == "UNPAUSE_DEPOSITS" and unpause["status"] == "executed"
    assert unpause["note"].startswith("approved by risk-officer")
    assert store.get_decision(DEC_ID).actions[7].status == "executed"
    resp = client.post(f"/api/decisions/{DEC_ID}/approve", json=body)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "action is not pending approval (status=executed)"}

    resp = client.post(f"/api/verify/{DEC_ID}")
    assert resp.status_code == 200 and resp.json()["match"] is True

    resp = client.post(f"/api/incidents/{INC_ID}/submit", json={"submitted_by": "compliance-officer"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["dora"]["submitted"] is True
    resp = client.post(f"/api/incidents/{INC_ID}/submit", json={"submitted_by": "compliance-officer"})
    assert resp.status_code == 409 and resp.json() == {"detail": "already submitted"}


def test_same_alert_twice_is_deduplicated(scenario):
    store, engine, alert, snap, _ = scenario
    engine.inject([alert], snap)
    assert [d.id for d in store.decisions()] == [DEC_ID]
    assert [i.id for i in store.incidents()] == [INC_ID]
