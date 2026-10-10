# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""Chain access (TASKS.md 2.1, T0). web3 and eth-account are imported inside the functions, so importing this
module never fails offline (T4 dry-run tests).

Assumed deployment JSON shape (deployments/<network>.json, written by T1; to be confirmed, CR-004):
    {"network": "local", "chain_id": 31337,
     "assets": {"USDC": "0x…", "WETH": "0x…", "rsETH": "0x…"},
     "lending": [{"id": "lend-eth", "address": "0x…"}, {"id": "lend-avax", "address": "0x…"}],
     "contracts": {"vault": "0x…", "oracle": "0x…", "registry": "0x…", "bridge": "0x…"}}
Assumed ABI files (abi/<Name>.json, raw list or {"abi": [...]}): Vault, LendingPool, PriceOracle,
EvidenceRegistry, Bridge, RsETH, MockERC20.
"""
from __future__ import annotations

import json
import threading

from backend import settings

_ABI_NAMES = {"vault": "Vault", "oracle": "PriceOracle", "registry": "EvidenceRegistry", "bridge": "Bridge"}
_W3_CACHE: dict[str, object] = {}
_SEND_LOCKS: dict[str, threading.Lock] = {}
_MODULE_LOCK = threading.Lock()


def _make_w3(url: str):
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))
    if settings.NETWORK == "fuji":
        try:
            from web3.middleware import ExtraDataToPOAMiddleware  # web3 7

            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except ImportError:
            from web3.middleware import geth_poa_middleware  # web3 6

            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3


def w3():
    """Cached Web3 on settings.RPC_URL; falls back to settings.RPC_FALLBACK_URL if the primary is not connected."""
    with _MODULE_LOCK:
        url = settings.RPC_URL
        if url not in _W3_CACHE:
            _W3_CACHE[url] = _make_w3(url)
        primary = _W3_CACHE[url]
        fallback_url = settings.RPC_FALLBACK_URL
    if fallback_url and not primary.is_connected():
        with _MODULE_LOCK:
            if fallback_url not in _W3_CACHE:
                _W3_CACHE[fallback_url] = _make_w3(fallback_url)
            return _W3_CACHE[fallback_url]
    return primary


def load_deployment() -> dict:
    """Re-read on every call (a redeploy is picked up without restart)."""
    path = settings.DEPLOYMENTS_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} not found (run make deploy)")
    return json.loads(path.read_text(encoding="utf-8"))


def load_abi(name: str) -> list:
    data = json.loads((settings.ABI_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data["abi"] if isinstance(data, dict) and "abi" in data else data


def _at(address: str, abi_name: str):
    web3 = w3()
    return web3.eth.contract(address=web3.to_checksum_address(address), abi=load_abi(abi_name))


def contract(name: str):
    return _at(load_deployment()["contracts"][name], _ABI_NAMES[name])


def token(symbol: str):
    return _at(load_deployment()["assets"][symbol], "RsETH" if symbol == "rsETH" else "MockERC20")


def lending(deployment_id: str):
    entry = next((x for x in load_deployment()["lending"] if x["id"] == deployment_id), None)
    if entry is None:
        raise KeyError(f"unknown lending deployment {deployment_id!r}")
    return _at(entry["address"], "LendingPool")


def vault():
    return contract("vault")


def bridge():
    return contract("bridge")


def oracle():
    return contract("oracle")


def registry():
    return contract("registry")


def account(role: str):
    from eth_account import Account

    return Account.from_key(settings.private_key(role))


def bot_accounts() -> list:
    from eth_account import Account

    return [Account.from_key(k) for k in settings.bot_pks()]


def _sender_lock(address: str) -> threading.Lock:
    with _MODULE_LOCK:
        return _SEND_LOCKS.setdefault(address.lower(), threading.Lock())


def send(fn, sender, value: int = 0) -> dict:
    """Build, sign, send and wait (120 s). Per-sender lock so concurrent callers never reuse a nonce."""
    web3 = w3()
    with _sender_lock(sender.address):
        tx = fn.build_transaction({
            "from": sender.address,
            "nonce": web3.eth.get_transaction_count(sender.address, "pending"),
            "value": value,
            "chainId": settings.CHAIN_ID,
        })
        tx["gas"] = int(web3.eth.estimate_gas(tx) * 1.3)
        signed = sender.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction  # web3 7 / web3 6
        tx_hash = web3.eth.send_raw_transaction(raw)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    hex_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not hex_hash.startswith("0x"):
        hex_hash = "0x" + hex_hash
    return {"tx_hash": hex_hash, "status": receipt["status"], "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"]}


def explorer_tx(tx_hash: str) -> str:
    return f"{settings.EXPLORER_URL}/tx/{tx_hash}"
