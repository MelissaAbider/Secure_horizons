"""Optional Bedrock drafting of the DORA Description paragraph (TASKS.md T5 6). Never blocking, never raises.

BEDROCK_MODEL_ID empty -> the deterministic template. At most one call per second; same facts -> cached text.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Literal

from backend import settings

logger = logging.getLogger("t5.llm")

SYSTEM = ("Write the Description paragraph of a DORA initial incident notification, in English, max 120 words, "
          "factual, using only the facts provided. Do not speculate on attribution. Do not invent numbers.")
MAX_CHARS = 1500

_LOCK = threading.Lock()
_CLIENT = None
_CACHE: dict[str, str] = {}
_LAST_CALL: float | None = None
_STATUS: Literal["ok", "degraded", "unknown"] = "unknown"


def reset() -> None:
    """Forget client, cache, rate-limit clock and status (tests)."""
    global _CLIENT, _LAST_CALL, _STATUS
    with _LOCK:
        _CLIENT, _LAST_CALL, _STATUS = None, None, "unknown"
        _CACHE.clear()


def enabled() -> bool:
    return settings.BEDROCK_MODEL_ID != ""


def last_status() -> Literal["ok", "degraded", "unknown"]:
    return _STATUS


def facts_key(facts: dict) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()


def cached(facts: dict) -> str | None:
    return _CACHE.get(facts_key(facts))


def _client():
    global _CLIENT
    if _CLIENT is None:
        import boto3
        from botocore.config import Config

        _CLIENT = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION,
                               config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 1}))
    return _CLIENT


def _fallback(fallback: str, reason: str) -> tuple[str, bool]:
    logger.warning("fallback reason=%s", reason)
    return fallback, False


def draft_description(facts: dict, fallback: str = "") -> tuple[str, bool]:
    """(text, ai_used). Any failure, empty or too long text -> (fallback, False)."""
    global _LAST_CALL, _STATUS
    if not enabled():
        return fallback, False
    key = facts_key(facts)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key], True
        if _LAST_CALL is not None:
            wait = 1.0 - (time.monotonic() - _LAST_CALL)
            if wait > 0:
                time.sleep(wait)
        _LAST_CALL = time.monotonic()
        try:
            resp = _client().converse(
                modelId=settings.BEDROCK_MODEL_ID,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": json.dumps(facts, sort_keys=True, default=str)}]}],
                inferenceConfig={"maxTokens": 400, "temperature": 0},
            )
            text = resp["output"]["message"]["content"][0]["text"].strip()
        except Exception as e:  # noqa: BLE001
            _STATUS = "degraded"
            return _fallback(fallback, type(e).__name__)
        if not text or len(text) > MAX_CHARS:
            _STATUS = "degraded"
            return _fallback(fallback, "empty" if not text else "too_long")
        _STATUS = "ok"
        _CACHE[key] = text
        return text, True
