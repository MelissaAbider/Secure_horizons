# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""Tests never reach the outside world: the real .env may hold a Discord webhook or AWS ids.
Each test starts with every external channel off; a test that needs one sets it explicitly (monkeypatch)."""
import pytest

from backend import settings


@pytest.fixture(autouse=True)
def _no_external_channels(monkeypatch):
    for name in ("ALERT_WEBHOOK_URL", "SNS_TOPIC_ARN", "EVIDENCE_BUCKET", "BEDROCK_MODEL_ID"):
        monkeypatch.setattr(settings, name, "")
