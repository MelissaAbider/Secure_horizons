"""Helpers for the T2 chain tests (TASKS.md T2 step 1). Owner: T2."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from backend import chain, settings


def local_chain_ready() -> bool:
    """True when NETWORK=local, anvil answers on chain id 31337 and deployments/local.json exists."""
    if settings.NETWORK != "local" or not settings.DEPLOYMENTS_FILE.exists():
        return False
    try:
        return chain.w3().is_connected() and chain.w3().eth.chain_id == 31337
    except Exception:
        return False


def evm_snapshot() -> str:
    return chain.w3().provider.make_request("evm_snapshot", [])["result"]


def evm_revert(snap_id: str) -> None:
    chain.w3().provider.make_request("evm_revert", [snap_id])


@contextmanager
def snapshot() -> Iterator[None]:
    """Run a block of code then put the chain back exactly as it was."""
    snap = evm_snapshot()
    try:
        yield
    finally:
        evm_revert(snap)
