"""T4-24: decisions, approve and verify routes (TASKS.md 2.9, T4 3.7)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import settings
from backend.api import response
from backend.executor import DryRunExecutor, get_executor
from backend.responder import Responder
from backend.tests.test_t4_fixtures import FakeStore, evidence_tmp, load_attack, make_alert  # noqa: F401


@pytest.fixture
def client(evidence_tmp, monkeypatch):
    store = FakeStore()
    app = FastAPI()
    app.include_router(response.router, prefix="/api")
    app.dependency_overrides[response.get_store] = lambda: store
    get_executor.cache_clear()
    yield TestClient(app), store
    get_executor.cache_clear()


def _r2_high(store, block):
    snap = load_attack(block)
    alert = make_alert("R2_LIQUIDITY_DROP", "high", snap, "lend-eth", "WETH", 375000.0)
    (d,) = Responder(store, DryRunExecutor()).handle([alert], snap)
    return d


def test_routes(client, evidence_tmp, monkeypatch):
    http, store = client

    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    fixture = settings.FIXTURES_DIR / "decisions.json"
    resp = http.get("/api/decisions")
    if fixture.exists():
        assert resp.status_code == 200
        assert len(resp.json()) == len(json.loads(fixture.read_text()))
    else:
        assert resp.status_code == 503

    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    d = _r2_high(store, 45201826)
    assert d.id == "DEC-fuji-45201826-1"
    assert (evidence_tmp / f"{d.id}.json").exists()
    assert [x["id"] for x in http.get("/api/decisions").json()] == [d.id]

    url = f"/api/decisions/{d.id}/approve"
    body = {"action_index": 2, "approver": "risk-officer", "approve": True}
    resp = http.post(url, json=body)
    assert resp.status_code == 200, resp.text
    action = resp.json()["actions"][2]
    assert action["status"] == "executed"
    assert action["amount"] == "150000000000000000000"
    assert action["note"].startswith("approved by risk-officer")
    assert store.get_decision(d.id).actions[2].status == "executed"
    approvals = json.loads((evidence_tmp / f"{d.id}.json").read_text())["approvals"]
    assert [(a["action_index"], a["approver"], a["approve"]) for a in approvals] == [(2, "risk-officer", True)]

    resp = http.post(url, json=body)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "action is not pending approval (status=executed)"}
    assert http.post(url, json={**body, "action_index": 0}).status_code == 409
    assert http.post(url, json={**body, "action_index": 9}).status_code == 400
    assert http.post("/api/decisions/DEC-fuji-1-1/approve", json=body).status_code == 404
    assert http.post(url, json={"action_index": 2, "approve": True}).status_code == 422

    second = _r2_high(store, 45201828)
    resp = http.post(f"/api/decisions/{second.id}/approve",
                     json={"action_index": 2, "approver": "risk-officer", "approve": False})
    assert resp.status_code == 200
    assert resp.json()["actions"][2]["status"] == "rejected"
    assert resp.json()["actions"][2]["note"].startswith("rejected by risk-officer;")

    resp = http.post(f"/api/verify/{d.id}")
    assert resp.status_code == 200
    assert resp.json()["match"] is True
    assert http.post("/api/verify/DEC-fuji-1-1").status_code == 404
