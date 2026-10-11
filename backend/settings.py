"""Environment settings (TASKS.md 2.1). Owner: T0. Started from the T4 shim (CR-002) and completed by T0.

Values are read once at import. Tests monkeypatch backend.settings.X and code reads settings.X at call time.
No key is ever written to disk: on the local anvil chain, roles fall back to anvil's public test accounts.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv is optional
    pass


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_CHAIN_IDS = {"local": 31337, "fuji": 43113}
_DEFAULT_RPC = {"local": "http://127.0.0.1:8545", "fuji": "https://api.avax-test.network/ext/bc/C/rpc"}

NETWORK: str = os.environ.get("NETWORK") or "local"
CHAIN_ID: int = int(os.environ.get("CHAIN_ID") or _CHAIN_IDS.get(NETWORK, 31337))
# FUJI_RPC_URL is kept for the variable already in .env.example.
RPC_URL: str = (
    os.environ.get("RPC_URL")
    or (os.environ.get("FUJI_RPC_URL") if NETWORK == "fuji" else None)
    or _DEFAULT_RPC.get(NETWORK, _DEFAULT_RPC["local"])
)
RPC_FALLBACK_URL: str = os.environ.get("RPC_FALLBACK_URL", "")
EXPLORER_URL: str = os.environ.get("EXPLORER_URL") or "https://testnet.snowtrace.io"

USE_FIXTURES: bool = _bool("USE_FIXTURES", True)
ENGINE_ENABLED: bool = _bool("ENGINE_ENABLED", False)
POLL_INTERVAL_S: float = float(os.environ.get("POLL_INTERVAL_S") or 2)
DRY_RUN_ACTIONS: bool = _bool("DRY_RUN_ACTIONS", True)

AWS_REGION: str = os.environ.get("AWS_REGION") or "us-east-1"
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")
ALERT_WEBHOOK_URL: str = os.environ.get("ALERT_WEBHOOK_URL", "")
EVIDENCE_BUCKET: str = os.environ.get("EVIDENCE_BUCKET", "")
BEDROCK_MODEL_ID: str = os.environ.get("BEDROCK_MODEL_ID", "")
ETH_ARCHIVE_RPC_URL: str = os.environ.get("ETH_ARCHIVE_RPC_URL", "")

CONFIG_DIR: Path = ROOT / "backend" / "config"
DATA_DIR: Path = Path(os.environ.get("DATA_DIR") or ROOT / "data")
FIXTURES_DIR: Path = ROOT / "fixtures"
ABI_DIR: Path = ROOT / "abi"
DEPLOYMENTS_FILE: Path = ROOT / "deployments" / f"{NETWORK}.json"


def runtime_dir() -> Path:
    """data/runtime/<network>/ : store files and the maintenance flag (TASKS.md 2.10)."""
    return DATA_DIR / "runtime" / NETWORK


# ---------- Keys (TASKS.md 2.1) ----------

ROLE_ENV = {
    "deployer": "DEPLOYER_PK",
    "owner": "OWNER_PK",
    "guardian": "GUARDIAN_PK",
    "protocol_guardian": "PROTOCOL_GUARDIAN_PK",
    "attacker": "ATTACKER_PK",
    "evidence": "EVIDENCE_PK",
}
ANVIL_INDEX = {"deployer": 0, "owner": 1, "guardian": 2, "protocol_guardian": 3, "attacker": 4, "evidence": 5}
ANVIL_BOT_INDEXES = (6, 7, 8)
_ANVIL_MNEMONIC = "test test test test test test test test test test test junk"  # anvil's public test mnemonic


def _anvil_key(index: int) -> str:
    from eth_account import Account

    Account.enable_unaudited_hdwallet_features()
    return Account.from_mnemonic(_ANVIL_MNEMONIC, account_path=f"m/44'/60'/0'/0/{index}").key.hex()


def private_key(role: str) -> str:
    """Private key of a role. On NETWORK=local, always the matching anvil test account (the .env keys are for fuji)."""
    if NETWORK == "local":
        return _anvil_key(ANVIL_INDEX[role])
    value = os.environ.get(ROLE_ENV[role], "")
    if value:
        return value
    raise RuntimeError(f"Missing {ROLE_ENV[role]} in .env for NETWORK={NETWORK}")


def bot_pks() -> list[str]:
    """Three normal users: BOT_PKS (comma separated) on fuji, anvil accounts 6, 7, 8 on local."""
    if NETWORK == "local":
        return [_anvil_key(i) for i in ANVIL_BOT_INDEXES]
    return [k.strip() for k in os.environ.get("BOT_PKS", "").split(",") if k.strip()]
