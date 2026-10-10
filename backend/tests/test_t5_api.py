"""T5-24 to T5-26: incident routes (TASKS.md 2.9, T5 9).

backend/store.py (T0) is not there yet: the store is injected with dependency_overrides[get_store]
instead of monkeypatching backend.store.store. If fixtures/incident.json is missing, fixture mode is
tested against a fixture written to tmp_path from our own factories.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import settings
from backend.api import incidents as api
from backend.incidents import dependency_statuses
from backend.tests.test_t5_factories import run_reacted_incident

TITLE = "# DORA initial notification (draft, human review required)"


@pytest.fixture
def reacted(monkeypatch):
    incident, store = run_reacted_incident(monkeypatch)
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    app.dependency_overrides[api.get_store] = lambda: store
    return TestClient(app), incident, store


def test_fixture_mode(reacted, monkeypatch, tmp_path):
    http, incident, store = reacted
    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    if not (settings.FIXTURES_DIR / "incident.json").exists():
        (tmp_path / "incident.json").write_text(json.dumps(incident.model_dump(mode="json")))
        (tmp_path / "dependencies.json").write_text(
            json.dumps([d.model_dump(mode="json") for d in dependency_statuses(store)]))
        monkeypatch.setattr(settings, "FIXTURES_DIR", tmp_path)
    fixture = json.loads((settings.FIXTURES_DIR / "incident.json").read_text())
    resp = http.get("/api/incidents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert http.get(f"/api/incidents/{fixture['id']}").status_code == 200
    unknown = http.get("/api/incidents/UNKNOWN")
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "incident not found"}
    report = http.get(f"/api/incidents/{fixture['id']}/report.md")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    submitted = http.post(f"/api/incidents/{fixture['id']}/submit", json={"submitted_by": "compliance-officer"})
    assert submitted.status_code == 200
    assert submitted.json()["dora"]["submitted"] is True
    assert http.get("/api/dependencies").status_code == 200


def test_live_mode(reacted, monkeypatch):
    http, incident, _ = reacted
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    listed = http.get("/api/incidents").json()
    assert [i["id"] for i in listed] == [incident.id]
    detail = http.get(f"/api/incidents/{incident.id}")
    assert detail.status_code == 200
    assert detail.json()["saved_usd"] == 1325000.0
    assert detail.json()["status"] == "contained"
    report = http.get(f"/api/incidents/{incident.id}/report.md")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    assert report.text.startswith(TITLE)
    deps = http.get("/api/dependencies").json()
    assert len(deps) == 9


def test_submit(reacted, monkeypatch):
    http, incident, store = reacted
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    url = f"/api/incidents/{incident.id}/submit"
    first = http.post(url, json={"submitted_by": "compliance-officer"})
    assert first.status_code == 200
    body = first.json()
    assert body["dora"]["submitted"] is True
    assert body["dora"]["submitted_by"] == "compliance-officer"
    assert body["dora"]["submitted_at"].endswith("Z")
    assert "submitted by compliance-officer" in body["dora"]["report_markdown"]
    assert any(e["text"] == "DORA initial notification submitted by compliance-officer" for e in body["timeline"])
    second = http.post(url, json={"submitted_by": "compliance-officer"})
    assert second.status_code == 409
    assert second.json() == {"detail": "already submitted"}
    assert http.post(url, json={"submitted_by": ""}).status_code == 422
    assert http.post("/api/incidents/UNKNOWN/submit", json={"submitted_by": "x"}).status_code == 404
    assert store.get_incident(incident.id).dora.submitted is True
