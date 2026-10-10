"""T0-04: every route of TASKS.md 2.9 answers, through the fixture fallbacks and through the main app."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import settings
from backend.api import _fixtures

GET_ROUTES = [
    "/api/health", "/api/state", "/api/series?deployment_id=lend-eth&asset=WETH", "/api/alerts", "/api/decisions",
    "/api/incidents", "/api/incidents/INC-20261011-001", "/api/incidents/INC-20261011-001/report.md",
    "/api/dependencies", "/api/demo/runs/RUN-20261011080000-attack-42", "/api/metrics",
]


@pytest.fixture
def fallback_client() -> TestClient:
    _fixtures.reset_memory()
    app = FastAPI()
    for router in (_fixtures.state, _fixtures.response, _fixtures.incidents, _fixtures.demo, _fixtures.metrics):
        app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize("path", GET_ROUTES)
def test_fallback_get_routes(fallback_client: TestClient, path: str) -> None:
    assert fallback_client.get(path).status_code == 200


def test_fallback_errors_and_writes(fallback_client: TestClient) -> None:
    c = fallback_client
    assert c.get("/api/incidents/UNKNOWN").status_code == 404
    assert c.post("/api/verify/DEC-unknown").status_code == 404
    assert c.post("/api/verify/DEC-fuji-45201812-1").json()["match"] is True
    body = {"action_index": 7, "approver": "treasury-signer-1", "approve": True}
    assert c.post("/api/decisions/DEC-fuji-45201812-1/approve", json=body).json()["actions"][7]["status"] == "approved"
    assert c.post("/api/decisions/DEC-fuji-45201812-1/approve", json=body).status_code == 409
    assert c.post("/api/decisions/DEC-fuji-45201812-1/approve", json={**body, "action_index": 99}).status_code == 400
    submit = c.post("/api/incidents/INC-20261011-001/submit", json={"submitted_by": "compliance"})
    assert submit.json()["dora"]["submitted"] is True
    assert c.post("/api/incidents/INC-20261011-001/submit", json={"submitted_by": "compliance"}).status_code == 409
    assert c.post("/api/incidents/INC-20261011-001/submit", json={"submitted_by": ""}).status_code == 422
    assert c.post("/api/demo/attack", json={"seed": 7, "variant": "slow"}).json()["seed"] == 7
    assert c.post("/api/demo/attack", json={"variant": "foo"}).status_code == 422
    assert c.get("/api/series?limit=5").json().__len__() == 5


def test_main_app_serves_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    from backend.main import app

    with TestClient(app) as client:
        for path in GET_ROUTES:
            assert client.get(path).status_code == 200, path
