"""Safe side of T10: keys, contract artifacts, Safe creation, and Safe transactions signed by the asset manager.

Keys. Nothing here is ever printed or written to disk.
- the asset manager (the front door, the Safe's only owner for now): SAFE_OWNER_PKS on fuji (no AVAX needed: it only
  signs); anvil account 10 on local. Several comma-separated keys plus SAFE_THRESHOLD turn the Safe into a multisig.
- operator (the teller window, the platform): OPERATOR_PK on fuji, anvil account 9 on local. It can only call
  SealedListModule.execute.
- relayer: the deployer pays gas for deployments and Safe transactions. It has no right on the Safe.
- the agent holds no key at all.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Sequence

from backend import chain, settings

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contracts" / "out"
STATE_DIR = Path(__file__).resolve().parent / "deployments"
ZERO = "0x0000000000000000000000000000000000000000"

# Canonical Safe v1.4.1 deployments (safe-global/safe-deployments), checked live on Fuji on 2026-10-11.
CANONICAL = {
    "fuji": {"SafeL2": "0x29fcB43b46531BcA003ddC8FCB67FFE91900C762",
             "SafeProxyFactory": "0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67"},
}
ANVIL_OPERATOR_INDEX = 9
ANVIL_OWNER_INDEXES = (10,)


def threshold() -> int:
    return int(os.environ.get("SAFE_THRESHOLD") or 1)


def front_door(threshold_: int, owners: int) -> str:
    """Who signs for the Safe: the asset manager alone for now, a multisig if SAFE_OWNER_PKS holds several keys."""
    return "the asset manager signs alone" if owners == 1 else f"{threshold_} of {owners} owners sign"


def owner_accounts() -> list:
    from eth_account import Account

    if settings.NETWORK == "local":
        keys = [settings._anvil_key(i) for i in ANVIL_OWNER_INDEXES]
    else:
        keys = [k.strip() for k in os.environ.get("SAFE_OWNER_PKS", "").split(",") if k.strip()]
        if len(keys) < threshold():
            raise RuntimeError(f"SAFE_OWNER_PKS needs at least {threshold()} keys in .env for NETWORK={settings.NETWORK}")
    return sorted((Account.from_key(k) for k in keys), key=lambda a: int(a.address, 16))


def operator_account():
    from eth_account import Account

    if settings.NETWORK == "local":
        return Account.from_key(settings._anvil_key(ANVIL_OPERATOR_INDEX))
    key = os.environ.get("OPERATOR_PK", "")
    if not key:
        raise RuntimeError(f"Missing OPERATOR_PK in .env for NETWORK={settings.NETWORK}")
    return Account.from_key(key)


# ---------- artifacts and contracts ----------

_ARTIFACTS = {"SafeL2": "SafeL2.sol", "SafeProxyFactory": "SafeProxyFactory.sol", "SealedListModule": "SealedListModule.sol"}


def artifact(name: str) -> dict[str, Any]:
    path = OUT / _ARTIFACTS[name] / f"{name}.json"
    if not path.exists():
        raise RuntimeError(f"{path.relative_to(ROOT)} missing: run make t1-build first")
    return json.loads(path.read_text())


def contract(name: str, address: str):
    from web3 import Web3

    return chain.w3().eth.contract(address=Web3.to_checksum_address(address), abi=artifact(name)["abi"])


def deploy(name: str, args: Sequence[Any], sender) -> tuple[str, str]:
    """Deploys from contracts/out. Returns (address, tx_hash)."""
    art = artifact(name)
    factory = chain.w3().eth.contract(abi=art["abi"], bytecode=art["bytecode"]["object"])
    receipt = chain.send(factory.constructor(*args), sender)
    address = chain.w3().eth.get_transaction_receipt(receipt["tx_hash"])["contractAddress"]
    return address, receipt["tx_hash"]


def load_state() -> dict[str, Any]:
    path = STATE_DIR / f"{settings.NETWORK}.json"
    if not path.exists():
        raise RuntimeError(f"{path.relative_to(ROOT)} missing: run make seal-deploy first")
    return json.loads(path.read_text())


def save_state(state: dict[str, Any]) -> Path:
    STATE_DIR.mkdir(exist_ok=True)
    path = STATE_DIR / f"{settings.NETWORK}.json"
    path.write_text(json.dumps(state, indent=2) + "\n")
    return path


# ---------- Safe ----------

def safe_singleton_and_factory(relayer) -> tuple[str, str]:
    """Canonical Safe 1.4.1 on fuji; on a fresh anvil, the same contracts compiled from contracts/lib."""
    known = CANONICAL.get(settings.NETWORK)
    if known:
        for name, address in known.items():
            if len(chain.w3().eth.get_code(address)) == 0:
                raise RuntimeError(f"no code at the canonical {name} {address} on {settings.NETWORK}")
        return known["SafeL2"], known["SafeProxyFactory"]
    singleton, _ = deploy("SafeL2", [], relayer)
    factory, _ = deploy("SafeProxyFactory", [], relayer)
    return singleton, factory


def create_safe(owners: Sequence[str], threshold_: int, singleton: str, factory_address: str, salt: int,
                relayer) -> tuple[str, str]:
    """A Safe proxy with these owners and threshold. Returns (safe address, tx_hash)."""
    template = contract("SafeL2", singleton)
    initializer = template.encode_abi("setup", args=[list(owners), threshold_, ZERO, b"", ZERO, ZERO, 0, ZERO])
    factory = contract("SafeProxyFactory", factory_address)
    receipt = chain.send(factory.functions.createProxyWithNonce(singleton, initializer, salt), relayer)
    full = chain.w3().eth.get_transaction_receipt(receipt["tx_hash"])
    from web3.logs import DISCARD

    created = factory.events.ProxyCreation().process_receipt(full, errors=DISCARD)  # other logs: the Safe's own events
    return created[0]["args"]["proxy"], receipt["tx_hash"]


def exec_safe_tx(safe_address: str, to: str, data: bytes, signers: Sequence, relayer) -> dict[str, Any]:
    """The front door: each signer signs the EIP-712 SafeTx hash, the relayer submits execTransaction.

    Returns the receipt plus the signed hash and the signer addresses (never the keys)."""
    from web3 import Web3

    safe = contract("SafeL2", safe_address)
    to = Web3.to_checksum_address(to)
    nonce = safe.functions.nonce().call()
    safe_tx_hash = safe.functions.getTransactionHash(to, 0, data, 0, 0, 0, 0, ZERO, ZERO, nonce).call()
    ordered = sorted(signers, key=lambda a: int(a.address, 16))  # the Safe wants ascending owner addresses
    signatures = b"".join(bytes(a.unsafe_sign_hash(safe_tx_hash).signature) for a in ordered)
    receipt = chain.send(safe.functions.execTransaction(to, 0, data, 0, 0, 0, 0, ZERO, ZERO, signatures), relayer)
    if receipt["status"] != 1:
        raise RuntimeError(f"Safe transaction {receipt['tx_hash']} failed")
    return {**receipt, "safe_tx_hash": Web3.to_hex(safe_tx_hash), "signers": [a.address for a in ordered]}
