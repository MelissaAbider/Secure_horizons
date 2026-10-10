# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T0 shim: backend/main.py wiring (engine -> responder -> incidents) and routes."""
from fastapi.testclient import TestClient

from backend.store import Store


def test_module_wiring():
    import backend.main as m

    assert m.responder.handle in m.engine._handlers
    assert m.incidents.handle in m.responder._handlers
    assert m.engine.store is m.store and m.responder.store is m.store and m.incidents.store is m.store


def test_routes_and_health():
    import backend.main as m

    paths = set(m.app.openapi()["paths"])
    assert {"/api/health", "/api/decisions", "/api/decisions/{decision_id}/approve", "/api/verify/{decision_id}",
            "/api/incidents", "/api/incidents/{incident_id}", "/api/incidents/{incident_id}/report.md",
            "/api/incidents/{incident_id}/submit", "/api/dependencies"} <= paths
    resp = TestClient(m.app).get("/api/health")
    assert resp.status_code == 200 and resp.json()["shim"] is True


def test_wire_fresh_store():
    import backend.main as m

    store = Store()
    engine, responder, incidents = m.wire(store)
    assert engine is not m.engine and engine.store is store
    assert engine._handlers == [responder.handle]
    assert responder._handlers == [incidents.handle]
