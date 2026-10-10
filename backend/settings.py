# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""Environment settings (TASKS.md 2.1). PROVISIONAL: written on branch Adam-(T4,-T5) while the T0 skeleton is missing
(CR-002, extended by the T0 shim, CR-004).

Private keys never live in this file or on disk: private_key(role) and bot_pks() read them from the environment
(DEPLOYER_PK, OWNER_PK, GUARDIAN_PK, PROTOCOL_GUARDIAN_PK, ATTACKER_PK, EVIDENCE_PK, BOT_PKS) or, on NETWORK=local
only, derive them from the public anvil mnemonic.

Values are read once at import. Tests monkeypatch backend.settings.X and code reads settings.X at call time.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv is optional for the shim
    pass


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_CHAIN_IDS = {"local": 31337, "fuji": 43113}

NETWORK: str = os.environ.get("NETWORK") or "local"
CHAIN_ID: int = int(os.environ.get("CHAIN_ID") or _CHAIN_IDS.get(NETWORK, 31337))
EXPLORER_URL: str = os.environ.get("EXPLORER_URL") or "https://testnet.snowtrace.io"

USE_FIXTURES: bool = _bool("USE_FIXTURES", True)
DRY_RUN_ACTIONS: bool = _bool("DRY_RUN_ACTIONS", True)

AWS_REGION: str = os.environ.get("AWS_REGION") or "us-east-1"
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")
ALERT_WEBHOOK_URL: str = os.environ.get("ALERT_WEBHOOK_URL", "")
EVIDENCE_BUCKET: str = os.environ.get("EVIDENCE_BUCKET", "")
BEDROCK_MODEL_ID: str = os.environ.get("BEDROCK_MODEL_ID", "")

CONFIG_DIR: Path = ROOT / "backend" / "config"
DATA_DIR: Path = Path(os.environ.get("DATA_DIR") or ROOT / "data")
FIXTURES_DIR: Path = ROOT / "fixtures"

# ---------- T0 shim additions (CR-004) ----------

RPC_URL: str = os.environ.get("RPC_URL") or (
    "http://127.0.0.1:8545" if NETWORK == "local"
    else os.environ.get("FUJI_RPC_URL") or "https://api.avax-test.network/ext/bc/C/rpc")
RPC_FALLBACK_URL: str = os.environ.get("RPC_FALLBACK_URL") or ""
ENGINE_ENABLED: bool = _bool("ENGINE_ENABLED", False)  # the shim engine detects nothing
POLL_INTERVAL_S: float = float(os.environ.get("POLL_INTERVAL_S") or 2)
DEPLOYMENTS_FILE: Path = ROOT / "deployments" / f"{NETWORK}.json"
ABI_DIR: Path = ROOT / "abi"

# Public anvil/hardhat test mnemonic (not a secret). Keys are derived from it at call time, never stored.
ANVIL_MNEMONIC = "test test test test test test test test test test test junk"
ROLE_INDEX = {"deployer": 0, "owner": 1, "guardian": 2, "protocol_guardian": 3, "attacker": 4, "evidence": 5}
BOT_INDEXES = (6, 7, 8)


def _derive(index: int) -> str:
    try:
        from eth_account import Account
    except ImportError as e:
        raise RuntimeError("eth-account is required to derive local anvil keys") from e
    Account.enable_unaudited_hdwallet_features()
    acct = Account.from_mnemonic(ANVIL_MNEMONIC, account_path=f"m/44'/60'/0'/0/{index}")
    return "0x" + bytes(acct.key).hex()


def private_key(role: str) -> str:
    """Key for a role: env <ROLE>_PK, else derived from the anvil mnemonic on local, else RuntimeError."""
    if role not in ROLE_INDEX:
        raise ValueError(f"unknown role {role!r}")
    env = os.environ.get(f"{role.upper()}_PK")
    if env:
        return env
    if NETWORK == "local":
        return _derive(ROLE_INDEX[role])
    raise RuntimeError(f"{role.upper()}_PK is not set for NETWORK={NETWORK}")


def bot_pks() -> list[str]:
    """Bot keys: env BOT_PKS (comma-separated), else 3 keys derived on local, else RuntimeError."""
    raw = os.environ.get("BOT_PKS") or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if keys:
        return keys
    if NETWORK == "local":
        return [_derive(i) for i in BOT_INDEXES]
    raise RuntimeError(f"BOT_PKS is not set for NETWORK={NETWORK}")
