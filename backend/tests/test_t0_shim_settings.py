# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T0 shim: settings.private_key / bot_pks and the added defaults."""
import os

import pytest

from backend import settings

ROLES_ENV = ["DEPLOYER_PK", "OWNER_PK", "GUARDIAN_PK", "PROTOCOL_GUARDIAN_PK", "ATTACKER_PK", "EVIDENCE_PK", "BOT_PKS"]


@pytest.fixture
def no_key_env(monkeypatch):
    for name in ROLES_ENV:
        monkeypatch.delenv(name, raising=False)


def test_local_anvil_addresses(monkeypatch, no_key_env):
    account = pytest.importorskip("eth_account").Account
    monkeypatch.setattr(settings, "NETWORK", "local")
    assert account.from_key(settings.private_key("deployer")).address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    assert account.from_key(settings.private_key("guardian")).address == "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"


def test_local_three_distinct_bots(monkeypatch, no_key_env):
    pytest.importorskip("eth_account")
    monkeypatch.setattr(settings, "NETWORK", "local")
    bots = settings.bot_pks()
    assert len(bots) == 3 and len(set(bots)) == 3
    roles = {settings.private_key(r) for r in settings.ROLE_INDEX}
    assert not roles & set(bots)


def test_fuji_without_key_raises(monkeypatch, no_key_env):
    monkeypatch.setattr(settings, "NETWORK", "fuji")
    with pytest.raises(RuntimeError):
        settings.private_key("guardian")
    with pytest.raises(RuntimeError):
        settings.bot_pks()


def test_env_key_and_bots_win(monkeypatch, no_key_env):
    monkeypatch.setattr(settings, "NETWORK", "fuji")
    monkeypatch.setenv("GUARDIAN_PK", "from-env")
    monkeypatch.setenv("BOT_PKS", " a, b ,,c ")
    assert settings.private_key("guardian") == "from-env"
    assert settings.bot_pks() == ["a", "b", "c"]


def test_unknown_role():
    with pytest.raises(ValueError):
        settings.private_key("nobody")


def test_defaults():
    if not os.environ.get("POLL_INTERVAL_S"):
        assert settings.POLL_INTERVAL_S == 2
    if not os.environ.get("ENGINE_ENABLED"):
        assert settings.ENGINE_ENABLED is False
    if not os.environ.get("RPC_URL") and settings.NETWORK == "local":
        assert settings.RPC_URL == "http://127.0.0.1:8545"
    assert settings.DEPLOYMENTS_FILE == settings.ROOT / "deployments" / f"{settings.NETWORK}.json"
    assert settings.ABI_DIR == settings.ROOT / "abi"
