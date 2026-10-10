"""T0-05: keys fall back to anvil's public test accounts on local only."""
from __future__ import annotations

import pytest

from backend import chain, settings

ANVIL = {
    "deployer": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "owner": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "guardian": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
}


def test_local_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NETWORK", "local")
    for role in ("DEPLOYER_PK", "OWNER_PK", "GUARDIAN_PK", "BOT_PKS"):
        monkeypatch.delenv(role, raising=False)
    for role, address in ANVIL.items():
        assert chain.account(role).address == address
    assert len(chain.bot_accounts()) == 3


def test_fuji_requires_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NETWORK", "fuji")
    monkeypatch.delenv("GUARDIAN_PK", raising=False)
    monkeypatch.delenv("BOT_PKS", raising=False)
    with pytest.raises(RuntimeError):
        settings.private_key("guardian")
    assert settings.bot_pks() == []
