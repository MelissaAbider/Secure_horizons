"""Shared web3 helpers (TASKS.md 2.4). Owner: T0.

Addresses come from deployments/<network>.json and ABIs from abi/<Contract>.json, both written by T1.
Every Python task goes through these functions: no task reloads ABIs or manages nonces on its own.
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from typing import Any

from backend import settings

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


@lru_cache(maxsize=1)
def w3():
    from web3 import Web3

    return Web3(Web3.HTTPProvider(settings.RPC_URL, request_kwargs={"timeout": 20}))


def load_deployment() -> dict[str, Any]:
    """deployments/<network>.json, re-read on every call so that a redeploy (make reset) is picked up."""
    with open(settings.DEPLOYMENTS_FILE, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_abi(name: str) -> list[dict[str, Any]]:
    with open(settings.ABI_DIR / f"{name}.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["abi"] if isinstance(data, dict) and "abi" in data else data


def _contract(abi_name: str, address: str):
    from web3 import Web3

    return w3().eth.contract(address=Web3.to_checksum_address(address), abi=load_abi(abi_name))


def token(symbol: str):
    """"USDC" | "WETH" | "rsETH"."""
    return _contract("RsETH" if symbol == "rsETH" else "MockERC20", load_deployment()["assets"][symbol])


def lending(deployment_id: str):
    """"lend-eth" | "lend-avax"."""
    entry = next((d for d in load_deployment()["lending"] if d["id"] == deployment_id), None)
    if entry is None:
        raise KeyError(f"unknown lending deployment {deployment_id!r}")
    return _contract("MiniLend", entry["address"])


def vault():
    return _contract("TreasuryVault", load_deployment()["contracts"]["TreasuryVault"])


def bridge():
    return _contract("MockBridge", load_deployment()["contracts"]["MockBridge"])


def oracle():
    return _contract("MockOracle", load_deployment()["contracts"]["MockOracle"])


def registry():
    return _contract("EvidenceRegistry", load_deployment()["contracts"]["EvidenceRegistry"])


def account(role: str):
    """"deployer" | "owner" | "guardian" | "protocol_guardian" | "attacker" | "evidence"."""
    from eth_account import Account

    return Account.from_key(settings.private_key(role))


def bot_accounts() -> list:
    from eth_account import Account

    return [Account.from_key(k) for k in settings.bot_pks()]


def send(fn, sender, value: int = 0) -> dict[str, Any]:
    """Build, sign, send a contract call and wait for the receipt.

    One lock per sender address avoids nonce clashes between threads.
    Returns {"tx_hash": "0x...", "status": 1|0, "block_number": int, "gas_used": int}.
    """
    from web3 import Web3

    with _locks_guard:
        lock = _locks.setdefault(sender.address, threading.Lock())
    client = w3()
    with lock:
        nonce = client.eth.get_transaction_count(sender.address, "pending")
        tx = fn.build_transaction({"from": sender.address, "nonce": nonce, "value": value, "chainId": settings.CHAIN_ID})
        tx["gas"] = int(client.eth.estimate_gas(tx) * 1.3)
        signed = sender.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = client.eth.send_raw_transaction(raw)
    receipt = client.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return {
        "tx_hash": Web3.to_hex(tx_hash),
        "status": int(receipt["status"]),
        "block_number": int(receipt["blockNumber"]),
        "gas_used": int(receipt["gasUsed"]),
    }


def explorer_tx(tx_hash: str) -> str:
    return f"{settings.EXPLORER_URL}/tx/{tx_hash}"
