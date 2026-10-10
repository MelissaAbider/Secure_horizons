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


def test_discord_payload(evidence_tmp):
    """Discord-formatted message: one red embed, the 8 actions, the evidence hash, no mentions, within limits."""
    (d,), alerts, _, _ = handle_r1_critical()
    p = notify.build_discord_payload(d, alerts)
    assert p["content"].startswith("🚨 **[CRITICAL] DEC-fuji-45201812-1**") and len(p["content"]) <= 2000
    (embed,) = p["embeds"]
    assert embed["color"] == 0xE53935
    assert embed["title"] == alerts[0].title and alerts[0].explanation in embed["description"]
    actions = next(f["value"] for f in embed["fields"] if f["name"] == "Actions")
    assert actions.count("\n") == 7 and "400,000 USDC" in actions and "150 WETH" in actions
    assert all(len(f["value"]) <= 1024 for f in embed["fields"]) and len(embed["fields"]) <= 25
    assert any(d.record_hash in f["value"] for f in embed["fields"])
    assert p["allowed_mentions"] == {"parse": []}


def test_discord_detection():
    assert notify.is_discord_webhook("https://discord.com/api/webhooks/1/abc")
    assert not notify.is_discord_webhook("https://hooks.slack.com/services/x")
    assert not notify.is_discord_webhook("https://discord.com.evil.example/api/webhooks/1/abc")
