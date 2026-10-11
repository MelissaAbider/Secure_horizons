"""Agent and replay routes through backend.main (shim app), offline."""
import pytest
from fastapi.testclient import TestClient

from backend import agent, evidence, settings
from backend import main as app_main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", True)
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    app_main.store.reset()
    agent.reset()
    yield TestClient(app_main.app)
    app_main.store.reset()


def test_propose_needs_a_snapshot(client):
    resp = client.post("/api/agent/propose", json={"message": "deposit WETH"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "no snapshot yet"}


def test_validation(client):
    assert client.post("/api/agent/propose", json={}).status_code == 422
    assert client.post("/api/agent/propose", json={"message": ""}).status_code == 422


def test_replay_then_propose(client):
    first = client.post("/api/demo/replay")
    assert first.status_code == 200
    body = first.json()
    assert body["decisions"] == ["DEC-fuji-45201812-1"]
    assert body["incidents"] == [{"id": "INC-20261011-001", "status": "contained", "saved_usd": 1325000.0}]
    assert body["latest_block"] == 45201880
    assert client.post("/api/demo/replay").json() == body  # idempotent
    assert len(client.get("/api/decisions").json()) == 1

    resp = client.post("/api/agent/propose", json={"message": agent.DEMO_MESSAGE})
    assert resp.status_code == 200
    result = resp.json()
    assert result["id"] == "AGT-45201880-1"
    assert result["proposal"]["source"] == "fallback"
    assert result["check"]["allowed"] is False
    assert any(r.startswith("active critical alert R1_BACKING_DROP") for r in result["check"]["reasons"])
    assert any(r.startswith("vault deposits are paused") for r in result["check"]["reasons"])
    assert len(result["record_hash"]) == 66

    listed = client.get("/api/agent/proposals")
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == ["AGT-45201880-1"]
    assert client.get("/api/health").status_code == 200


def test_replay_refused_outside_dry_run(client, monkeypatch):
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    assert client.post("/api/demo/replay").status_code == 409
