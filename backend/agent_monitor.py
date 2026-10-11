"""R7_AGENT_LLM: a reactive LLM analyst that watches the same snapshot window as the deterministic rules (T3).

Third, independent surveillance layer next to R1-R5 (rules) and R6 (ML). Guardrails, from docs/product/INVARIANTS.md:
- read-only: the agent receives structured snapshots only, never free text from a channel, and holds no key;
- its output is strict JSON validated by Pydantic; anything else is discarded and logged as a data issue;
- severity is capped at "high": only deterministic rules may produce "critical";
- an alert from this layer never triggers a fund movement on its own: backend/consensus.py decides what is forwarded;
- the prompt is frozen on disk and hashed into every alert (`rules_version` = rules hash + prompt hash);
- Bedrock is optional: with an empty BEDROCK_MODEL_ID the layer is disabled and reports itself as unavailable.
  Any exception, timeout or malformed answer is swallowed: the engine never blocks and never infers safety from silence.
- at most one call per second, with a cache keyed on the window content, so a quiet chain costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend import settings
from backend.models import Alert, Snapshot

log = logging.getLogger("backend.agent_monitor")
RULE_ID = "R7_AGENT_LLM"
PROMPT_PATH = settings.CONFIG_DIR / "agent_prompt.md"
MAX_SEVERITY = "high"
_SEVERITY_RANK = {"none": -1, "info": 0, "warning": 1, "high": 2, "critical": 3}


class AgentVerdict(BaseModel):
    severity: Literal["none", "warning", "high"]
    phases: list[int] = Field(default_factory=list)
    deployment_id: Optional[str] = None
    asset: Optional[str] = None
    reasoning: str = Field(max_length=600)
    evidence: dict[str, str] = Field(default_factory=dict)

    @field_validator("phases")
    @classmethod
    def _phases(cls, v: list[int]) -> list[int]:
        if any(p not in (1, 2, 3, 4, 5) for p in v):
            raise ValueError("phase out of range")
        return sorted(set(v))

    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, v) -> dict[str, str]:
        if not isinstance(v, dict) or len(v) > 12:
            raise ValueError("evidence must be an object with at most 12 fields")
        # Models legitimately put numbers/bools here; coerce scalars to text, reject nested structures.
        out = {}
        for k, val in v.items():
            if isinstance(val, (dict, list)):
                raise ValueError("nested evidence not allowed")
            out[str(k)[:64]] = str(val)[:128]
        return out


@dataclass
class AgentStatus:
    enabled: bool = False
    available: bool = False
    last_error: Optional[str] = None
    calls: int = 0
    rejected: int = 0
    cache_hits: int = 0
    last_verdict: Optional[dict] = None
    prompt_hash: str = ""
    issues: list[str] = field(default_factory=list)


def prompt_hash(path=PROMPT_PATH) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _compact(snapshot: Snapshot) -> dict:
    """Numbers only, no addresses the model could echo as fake evidence beyond ids/symbols."""
    return {
        "block": snapshot.block_number, "time": snapshot.block_time.isoformat(),
        "tokens": [{"symbol": t.symbol, "bridge_source_locked": t.bridge_source_locked, "bridge_destination_released": t.bridge_destination_released,
                    "bridge_source_nonce": t.bridge_source_nonce, "bridge_destination_nonce": t.bridge_destination_nonce,
                    "bridge_paused": t.bridge_paused} for t in snapshot.tokens],
        "reserves": [{"deployment_id": r.deployment_id, "asset": r.asset, "available_liquidity": r.available_liquidity,
                      "total_collateral": r.total_collateral, "total_borrowed": r.total_borrowed, "utilization_bps": r.utilization_bps,
                      "borrow_apy_bps": r.borrow_apy_bps, "frozen": r.frozen, "paused": r.paused} for r in snapshot.reserves],
        "positions": [{"deployment_id": p.deployment_id, "asset": p.asset, "supplied": p.supplied, "withdrawable_now": p.withdrawable_now,
                       "withdrawable_ratio_bps": p.withdrawable_ratio_bps, "value_usd": p.value_usd} for p in snapshot.positions],
        "vault": {"deposits_paused": snapshot.vault.deposits_paused},
    }


def build_messages(window: list[Snapshot], max_snapshots: int = 8) -> tuple[str, str]:
    """System prompt + user content. Only the last `max_snapshots` are sent, the first one as a baseline."""
    system = PROMPT_PATH.read_text(encoding="utf-8")
    sel = window[-max_snapshots:] if len(window) <= max_snapshots else [window[0], *window[-(max_snapshots - 1):]]
    user = json.dumps({"snapshots": [_compact(s) for s in sel]}, separators=(",", ":"))
    return system, user


def _extract_json(text: str) -> dict | None:
    """First complete JSON object in the answer, tolerant to ```json fences and surrounding prose. Returns a dict or None."""
    text = re.sub(r"```(?:json)?", "", text)
    decoder = json.JSONDecoder()
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def parse_verdict(text: str, snapshot: Snapshot) -> AgentVerdict:
    """Strict parse. Raises ValueError for anything that is not a well-formed, grounded verdict."""
    payload = _extract_json(text)
    if payload is None:
        raise ValueError("no JSON object in answer")
    try:
        verdict = AgentVerdict.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"schema: {exc.error_count()} error(s)") from exc
    known_dep = {r.deployment_id for r in snapshot.reserves} | {p.deployment_id for p in snapshot.positions}
    known_asset = {r.asset for r in snapshot.reserves} | {t.symbol for t in snapshot.tokens}
    if verdict.deployment_id is not None and verdict.deployment_id not in known_dep:
        raise ValueError("hallucinated deployment_id")
    if verdict.asset is not None and verdict.asset not in known_asset:
        raise ValueError("hallucinated asset")
    if verdict.severity != "none" and not verdict.phases:
        raise ValueError("severity without observed phase")
    return verdict


def _bedrock_call(system: str, user: str, model_id: str, region: str) -> str:
    import boto3
    client = boto3.client("bedrock-runtime", region_name=region)
    resp = client.converse(modelId=model_id, system=[{"text": system}], messages=[{"role": "user", "content": [{"text": user}]}],
                           inferenceConfig={"maxTokens": 800, "temperature": 0})
    return "".join(part.get("text", "") for part in resp["output"]["message"]["content"])


class AgentMonitor:
    """Evaluate a window with the LLM. Thread-safe, rate-limited, cached, never raises from `evaluate`."""

    def __init__(self, cfg: dict, call: Callable[[str, str], str] | None = None, clock: Callable[[], float] = time.monotonic,
                 timeout_s: float = 8.0, min_interval_s: float = 1.0):
        self.cfg = cfg
        self.status = AgentStatus(enabled=bool(settings.BEDROCK_MODEL_ID) or call is not None, prompt_hash=prompt_hash())
        self._live_provider = call is None
        self._call = call or (lambda s, u: _bedrock_call(s, u, settings.BEDROCK_MODEL_ID, settings.AWS_REGION))
        self._clock, self._timeout, self._min_interval = clock, timeout_s, min_interval_s
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-llm")
        self._lock = threading.Lock()
        self._cache: dict[str, AgentVerdict] = {}
        self._last_call = -1e9
        self._version = f"{cfg['_version']}+prompt:{self.status.prompt_hash[7:19]}"

    def _key(self, user: str) -> str:
        return hashlib.sha256(user.encode()).hexdigest()

    def evaluate(self, window: list[Snapshot]) -> tuple[list[Alert], list[str]]:
        """Returns (alerts, issues). Empty alerts with a non-empty issue list means 'unavailable', not 'safe'."""
        if not self.status.enabled:
            self.status.available = False
            return [], ["R7 agent disabled: BEDROCK_MODEL_ID empty"]
        if not window:
            return [], ["R7 agent: no snapshot"]
        snapshot = window[-1]
        if self._live_provider and snapshot.source != "live":
            return [], ["R7 agent: live provider skipped for fixture/replay input"]
        try:
            system, user = build_messages(window)
        except Exception as exc:
            self.status.last_error = type(exc).__name__
            return [], ["R7 agent: prompt unavailable"]
        key = self._key(user)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self.status.cache_hits += 1
                return self._to_alerts(cached, snapshot), []
            wait = self._min_interval - (self._clock() - self._last_call)
            if wait > 0:
                return [], ["R7 agent: rate limited, verdict pending"]
            self._last_call = self._clock()
        try:
            text = self._pool.submit(self._call, system, user).result(timeout=self._timeout)
            self.status.calls += 1
            verdict = parse_verdict(text, snapshot)
        except FutureTimeout:
            self.status.last_error, self.status.available = "Timeout", False
            return [], ["R7 agent: timeout, verdict unavailable"]
        except ValueError as exc:
            self.status.rejected += 1
            self.status.last_error, self.status.available = f"Rejected: {exc}", True
            log.warning("R7 verdict rejected (%s)", exc)
            return [], ["R7 agent: answer rejected (malformed or ungrounded)"]
        except Exception as exc:
            self.status.last_error, self.status.available = type(exc).__name__, False
            log.warning("R7 agent call failed (%s)", type(exc).__name__)
            return [], ["R7 agent: provider error, verdict unavailable"]
        self.status.available, self.status.last_error = True, None
        self.status.last_verdict = verdict.model_dump()
        with self._lock:
            if len(self._cache) > 256:
                self._cache.clear()
            self._cache[key] = verdict
        return self._to_alerts(verdict, snapshot), []

    def _to_alerts(self, verdict: AgentVerdict, s: Snapshot) -> list[Alert]:
        if verdict.severity == "none":
            return []
        severity = verdict.severity if _SEVERITY_RANK[verdict.severity] <= _SEVERITY_RANK[MAX_SEVERITY] else MAX_SEVERITY
        # Exposure = treasury value in the concerned deployment (the collateral asset itself is rarely our position).
        exposure = sum(p.value_usd for p in s.positions if verdict.deployment_id in (None, p.deployment_id))
        return [Alert(id=f"ALT-{s.network}-{s.block_number}-{RULE_ID}-{verdict.deployment_id or 'global'}-{verdict.asset or 'all'}",
                      rule_id=RULE_ID, severity=severity, network=s.network, deployment_id=verdict.deployment_id, asset=verdict.asset,
                      block_number=s.block_number, block_time=s.block_time, detected_at=s.block_time,
                      title=f"LLM analyst: KelpDAO pattern phases {verdict.phases}",
                      explanation=verdict.reasoning,
                      metrics={"phases": [str(p) for p in verdict.phases], "layer": "llm", **{f"evidence.{k}": v for k, v in verdict.evidence.items()}},
                      exposure_usd=round(exposure, 2), rules_version=self._version)]

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
