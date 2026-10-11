import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.api import feedback as feedback_api
from backend.feedback import FeedbackLedger, FeedbackRequest
from backend.main import app
from backend.models import Alert
from backend.tests.test_t3_rules import load_series


def alert(block=1, rule_id="R6_ML_ANOMALY"):
    s = load_series("snapshots_attack.jsonl")[0]
    return Alert(id=f"ALT-fuji-{block}-{rule_id}-global-all", rule_id=rule_id, severity="high", network="fuji",
                 deployment_id=None, asset=None, block_number=block, block_time=s.block_time,
                 detected_at=datetime.now(timezone.utc), title="anomaly", explanation="state deviated",
                 metrics={"layer": "ml", "score": 4.2, "threshold": 2.0}, exposure_usd=100.0,
                 rules_version="rules-v+ml:model-v")


def request(label="confirmed_attack", request_id=None):
    return FeedbackRequest(label=label, reviewer="analyst@example", reason_code="bridge_mismatch",
                           note="reviewed against source and destination transactions", request_id=request_id)


def test_observation_is_idempotent_and_hash_chain_verifies(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    s = load_series("snapshots_attack.jsonl")[0]
    first = ledger.observe(alert(), s)
    same = ledger.observe(alert(), s)
    assert first.event_id == same.event_id
    assert len(ledger.views()) == 1
    assert ledger.verify() == (True, [])
    view = ledger.views()[0]
    assert view.observation["layer"] == "ml"
    assert view.observation["context"]["block"] == s.block_number
    serialized = (tmp_path / "alert_feedback.jsonl").read_text()
    assert s.vault.address.lower() not in serialized.lower()


def test_review_history_is_append_only_and_latest_is_current(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    ledger.observe(alert(), load_series("snapshots_attack.jsonl")[0])
    first = ledger.review(alert().id, request("uncertain"))
    second = ledger.review(alert().id, request("confirmed_attack"))
    view = ledger.views()[0]
    assert len(view.reviews) == 2
    assert view.current_review["label"] == "confirmed_attack"
    assert first.record_hash != second.record_hash
    assert ledger.verify()[0]


def test_request_id_makes_review_retry_idempotent(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    ledger.observe(alert(), load_series("snapshots_attack.jsonl")[0])
    one = ledger.review(alert().id, request(request_id="ticket-42"))
    two = ledger.review(alert().id, request(request_id="ticket-42"))
    assert one.event_id == two.event_id
    assert len(ledger.views()[0].reviews) == 1


def test_review_requires_existing_observation(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    try:
        ledger.review("missing", request())
        assert False
    except KeyError:
        pass


def test_tampering_is_detected(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    ledger.observe(alert(), load_series("snapshots_attack.jsonl")[0])
    path = tmp_path / "alert_feedback.jsonl"
    row = json.loads(path.read_text().splitlines()[0])
    row["payload"]["severity"] = "info"
    path.write_text(json.dumps(row) + "\n")
    valid, errors = ledger.verify()
    assert not valid and any("record hash mismatch" in error for error in errors)


def test_export_contains_only_reviewed_rows_and_never_changes_model(tmp_path):
    ledger = FeedbackLedger(tmp_path)
    s = load_series("snapshots_attack.jsonl")[0]
    ledger.observe(alert(1), s)
    ledger.observe(alert(2, "R7_AGENT_LLM"), s)
    assert ledger.export_training_rows() == []
    ledger.review(alert(1).id, request("legitimate_activity"))
    rows = ledger.export_training_rows()
    assert len(rows) == 1
    assert rows[0]["label"] == "legitimate_activity" and rows[0]["version"] == "rules-v+ml:model-v"
    assert "model" not in ledger.__dict__


def test_handler_failure_cannot_block_detection(tmp_path, monkeypatch):
    ledger = FeedbackLedger(tmp_path)
    monkeypatch.setattr(ledger, "observe", lambda a, s: (_ for _ in ()).throw(OSError("disk full")))
    ledger.handle([alert()], load_series("snapshots_attack.jsonl")[0])


def test_feedback_api_history_review_integrity_and_export(tmp_path, monkeypatch):
    ledger = FeedbackLedger(tmp_path)
    ledger.observe(alert(), load_series("snapshots_attack.jsonl")[0])
    monkeypatch.setattr(feedback_api, "get_ledger", lambda: ledger)
    client = TestClient(app)
    payload = {"label": "confirmed_attack", "reviewer": "alice", "reason_code": "bridge_mismatch", "note": "verified", "request_id": "case-1"}
    response = client.post(f"/api/alerts/{alert().id}/feedback", json=payload)
    assert response.status_code == 200 and response.json()["event_type"] == "review"
    history = client.get("/api/feedback").json()
    assert history[0]["current_review"]["label"] == "confirmed_attack"
    integrity = client.get("/api/feedback/integrity").json()
    assert integrity == {"valid": True, "errors": [], "training_side_effect": False}
    export = client.get("/api/feedback/export").json()
    assert export["count"] == 1 and export["active_model_changed"] is False


def test_feedback_api_rejects_invalid_label_and_missing_alert(tmp_path, monkeypatch):
    ledger = FeedbackLedger(tmp_path)
    monkeypatch.setattr(feedback_api, "get_ledger", lambda: ledger)
    client = TestClient(app)
    bad = client.post("/api/alerts/x/feedback", json={"label": "yes", "reviewer": "a", "reason_code": "other"})
    assert bad.status_code == 422
    missing = client.post("/api/alerts/x/feedback", json={"label": "uncertain", "reviewer": "alice", "reason_code": "other"})
    assert missing.status_code == 404
