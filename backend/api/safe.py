"""Safe routes for the dashboard (T10): connect a wallet, sign the owner's Safe transactions, allocate. Owner: T10.

The owner's signature comes from the browser wallet (eth_signTypedData_v4); the platform checks it and relays.
One chain write at a time, and none while a demo run (attack or reset) is using the deployer key.
"""
from __future__ import annotations

import threading
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
_WRITE = threading.Lock()
_PENDING: dict[str, dict] = {}  # safe_tx_hash -> the request the wallet was asked to sign


class ConnectBody(BaseModel):
    owner: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")


class PrepareBody(BaseModel):
    action: Literal["enable_module", "seal"]
    integrations: list[str] = Field(default_factory=list)


class SubmitBody(BaseModel):
    safe_tx_hash: str
    signature: str = Field(pattern=r"^0x[0-9a-fA-F]{130}$")


class AllocateBody(BaseModel):
    integration: str
    action: Literal["deposit", "withdraw"]
    amount: str = Field(pattern=r"^(max|[0-9]+(\.[0-9]+)?)$")


def _guarded(fn):
    from backend.api import demo

    if any(r.status == "running" for r in demo._RUNS.values()):
        raise HTTPException(409, "a demo run (attack or reset) is in progress: try again when it is done")
    if not _WRITE.acquire(blocking=False):
        raise HTTPException(409, "another Safe operation is in progress")
    try:
        return fn()
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:  # missing key or Safe state on this machine: say which, never the value
        raise HTTPException(503, str(exc)) from exc
    finally:
        _WRITE.release()


@router.get("/safe")
def safe_status() -> dict:
    from sealed import live

    try:
        return live.status()
    except Exception as exc:  # chain unreachable or deployment missing
        raise HTTPException(503, f"chain not ready: {type(exc).__name__}") from exc


@router.post("/safe/connect")
def safe_connect(body: ConnectBody) -> dict:
    from sealed import live

    return _guarded(lambda: live.connect(body.owner))


@router.post("/safe/prepare")
def safe_prepare(body: PrepareBody) -> dict:
    from sealed import live

    request = _guarded(lambda: live.prepare(body.action, body.integrations))
    _PENDING[request["safe_tx_hash"]] = request
    return request


@router.post("/safe/submit")
def safe_submit(body: SubmitBody) -> dict:
    from sealed import live

    request: Optional[dict] = _PENDING.get(body.safe_tx_hash)
    if request is None:
        raise HTTPException(404, "unknown or expired request: prepare it again")
    result = _guarded(lambda: live.submit(request, body.signature))
    _PENDING.pop(body.safe_tx_hash, None)
    return result


@router.post("/safe/fund")
def safe_fund() -> dict:
    from sealed import live
    from sealed import safe as S

    return _guarded(lambda: {"txs": live.fund(S.load_state()), "status": live.status()})


@router.post("/safe/allocate")
def safe_allocate(body: AllocateBody) -> dict:
    from sealed import live

    return _guarded(lambda: live.allocate(body.integration, body.action, body.amount))
