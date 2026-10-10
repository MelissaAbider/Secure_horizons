"""T4-19, T4-20: notifications (TASKS.md T4 3.4)."""
import boto3

from backend import notify, settings
from backend.tests.test_t4_fixtures import evidence_tmp, handle_r1_critical  # noqa: F401


def test_notify_never_raises(evidence_tmp, monkeypatch):
    (d,), alerts, _, _ = handle_r1_critical()
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:not-a-topic")

    def broken_client(*args, **kwargs):
        raise RuntimeError("no AWS in tests")

    monkeypatch.setattr(boto3, "client", broken_client)
    assert notify.notify(d, alerts) == ["log", "webhook", "sns"]
    for thread in notify.SENT_THREADS:
        thread.join(timeout=5)


def test_payload(evidence_tmp):
    (d,), alerts, _, _ = handle_r1_critical()
    payload = notify.build_payload(d, alerts)
    for key in ("text", "content", "decision_id", "network", "block_number", "exposure_usd", "matrix_cell", "actions"):
        assert key in payload
    assert payload["severity"] == "critical"
    assert payload["decision_id"] == "DEC-fuji-45201812-1"
    assert len(payload["alerts"]) == 1
    assert payload["text"] == payload["content"]
