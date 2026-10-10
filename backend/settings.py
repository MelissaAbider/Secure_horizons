"""Environment settings (TASKS.md 2.1). PROVISIONAL: minimal version written on branch Adam-(T4,-T5)
while the T0 skeleton is missing. No private keys here: private_key(role) and bot_pks() belong to T0.

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
