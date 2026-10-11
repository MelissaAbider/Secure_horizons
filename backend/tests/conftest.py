"""Shared test guard: the Discord bot settings from .env never reach a test (no network)."""
import pytest


@pytest.fixture(autouse=True)
def _no_discord_bot(monkeypatch):
    for name in ("DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID", "DISCORD_PUBLIC_KEY", "DISCORD_ALLOWED_USER_IDS"):
        monkeypatch.delenv(name, raising=False)
