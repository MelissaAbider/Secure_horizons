"""The sealed list for a connected wallet (T10, dashboard). Used by backend/api/safe.py.

The asset manager connects a browser wallet (Rabby). The platform creates a Safe owned by that address alone
(1 of 1) and its teller-window module, and credits the Safe with test tokens. The manager then signs, in the wallet,
the two Safe transactions only an owner can make: enable the module, seal the list (the Merkle root). The platform
relays them and pays the gas: it never holds the manager's key. Allocations go through the teller window.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from backend import chain, settings
from sealed import safe as S
from sealed import teller
from sealed.deploy import fund_operator
from sealed.seal import available_integrations, operations, parse_integration
from sealed.tree import MerkleTree

TEST_FUNDS = {"USDC": 1_000_000, "WETH": 500}  # what the Safe holds after "fund" (human units, test tokens)


def _state() -> Optional[dict[str, Any]]:
    return S.load_state() if (S.STATE_DIR / f"{settings.NETWORK}.json").exists() else None


def _units(symbol: str, amount: int) -> int:
    return amount * 10 ** chain.token(symbol).functions.decimals().call()


def seal_status(state: dict[str, Any], on_chain_root: str) -> str:
    """none: nothing sealed; stale: the markets were redeployed (make reset) or the root moved; sealed: in force."""
    sealed = state.get("sealed")
    if not sealed:
        return "none"
    try:
        rebuilt = "0x" + MerkleTree([op.leaf for op in operations(sealed.get("integrations") or sealed["protocols"],
                                                                     state["safe"])]).root.hex()
    except ValueError:
        return "stale"
    return "sealed" if rebuilt == sealed["root"] == on_chain_root else "stale"


def status() -> dict[str, Any]:
    dep = chain.load_deployment()
    out: dict[str, Any] = {"network": settings.NETWORK, "chain_id": settings.CHAIN_ID, "explorer_url": settings.EXPLORER_URL,
                           "integrations_available": [{k: x[k] for k in ("id", "protocol", "asset", "label")}
                                                      for x in available_integrations(dep)],
                           "connected": False}
    state = _state()
    if not state or not len(chain.w3().eth.get_code(state["safe"])):
        return out
    safe = S.contract("SafeL2", state["safe"])
    module = S.contract("SealedListModule", state["module"])
    root = "0x" + module.functions.root().call().hex()
    balances = {a: str(chain.token(a).functions.balanceOf(state["safe"]).call()) for a in TEST_FUNDS}
    positions = []
    for m in dep["lending"]:
        for a in TEST_FUNDS:
            supplied = chain.lending(m["id"]).functions.getUserSupplied(state["safe"], dep["assets"][a]).call()
            if supplied:
                positions.append({"integration": f"{m['id']}:{a}", "supplied": str(supplied)})
    sealed = state.get("sealed") or {}
    out.update(connected=True, owner=state["owners"][0], safe=state["safe"], module=state["module"],
               operator=state["operator"], module_enabled=safe.functions.isModuleEnabled(state["module"]).call(),
               root=root, seal_status=seal_status(state, root),
               sealed_integrations=sealed.get("integrations") or [f"{p}:USDC" for p in sealed.get("protocols", [])],
               seal_tx=sealed.get("tx_hash"), balances=balances, positions=positions,
               decimals={a: chain.token(a).functions.decimals().call() for a in TEST_FUNDS})
    return out


def fund(state: dict[str, Any]) -> list[str]:
    """Tops the Safe up to the test amounts on the current token contracts (the deployer owns the test tokens)."""
    deployer, txs = chain.account("deployer"), []
    for symbol, amount in TEST_FUNDS.items():
        token = chain.token(symbol)
        missing = _units(symbol, amount) - token.functions.balanceOf(state["safe"]).call()
        if missing > 0:
            txs.append(chain.send(token.functions.mint(state["safe"], missing), deployer)["tx_hash"])
    return txs


def connect(owner: str) -> dict[str, Any]:
    """The Safe of this owner: reused when it exists, otherwise created (1 of 1) with its module, then funded."""
    from web3 import Web3

    owner = Web3.to_checksum_address(owner)
    state = _state()
    reuse = state and state["owners"] == [owner] and len(chain.w3().eth.get_code(state["safe"]))
    relayer = chain.account("deployer")
    txs: dict[str, str] = {}
    if not reuse:
        operator = S.operator_account()
        fund_operator(operator, relayer)
        singleton, factory = S.safe_singleton_and_factory(relayer)
        safe_address, txs["create_safe"] = S.create_safe([owner], 1, singleton, factory, int(time.time()), relayer)
        module_address, txs["deploy_module"] = S.deploy("SealedListModule", [safe_address, operator.address], relayer)
        safe = S.contract("SafeL2", safe_address)
        state = {"network": settings.NETWORK, "chain_id": settings.CHAIN_ID, "explorer": settings.EXPLORER_URL,
                 "deployed_at_block": chain.w3().eth.block_number, "safe": safe_address,
                 "safe_version": safe.functions.VERSION().call(), "safe_singleton": singleton, "safe_factory": factory,
                 "owners": [owner], "threshold": 1, "module": module_address, "operator": operator.address,
                 "root": "0x" + "00" * 32, "txs": txs, "sealed": None,
                 "assets": {a: chain.load_deployment()["assets"][a] for a in TEST_FUNDS}}
        S.save_state(state)
    fund(state)
    return status()


def prepare(action: str, integrations: Optional[list[str]] = None) -> dict[str, Any]:
    """The SafeTx the owner signs: enable the module, or seal the root of the ticked integrations."""
    state = S.load_state()
    if action == "enable_module":
        data = S.contract("SafeL2", state["safe"]).encode_abi("enableModule", args=[state["module"]])
        request = S.safe_tx_request(state["safe"], state["safe"], data)
        request["summary"] = "Enable the teller-window module on your Safe"
    elif action == "seal":
        ids = [":".join(parse_integration(i)) for i in integrations or []]
        if not ids:
            raise ValueError("tick at least one integration")
        ops = operations(ids, state["safe"])
        tree = MerkleTree([op.leaf for op in ops])
        data = S.contract("SealedListModule", state["module"]).encode_abi("setRoot", args=[tree.root])
        request = S.safe_tx_request(state["safe"], state["module"], data)
        request.update(summary=f"Seal {len(ops)} operations ({', '.join(ids)})", integrations=ids,
                       root="0x" + tree.root.hex(), leaves=[op.to_json() for op in ops])
    else:
        raise ValueError(f"unknown action {action!r}")
    request["action"] = action
    return request


def submit(request: dict[str, Any], signature: str) -> dict[str, Any]:
    state = S.load_state()
    receipt = S.submit_signed_safe_tx(request, signature, state["owners"][0], chain.account("deployer"))
    if request["action"] == "enable_module":
        state["txs"]["enable_module"] = receipt["tx_hash"]
    else:
        state["root"] = request["root"]
        state["sealed"] = {"protocols": sorted({parse_integration(i)[0] for i in request["integrations"]}),
                           "integrations": request["integrations"], "root": request["root"], "leaves": request["leaves"],
                           "safe_tx_hash": receipt["safe_tx_hash"], "signers": receipt["signers"],
                           "tx_hash": receipt["tx_hash"], "block": receipt["block_number"]}
    S.save_state(state)
    return {"tx_hash": receipt["tx_hash"], "block": receipt["block_number"], "status": status()}


def allocate(integration: str, action: str, amount: str) -> dict[str, Any]:
    """Deposit or withdraw through the teller window: refused off-chain when not in the sealed list."""
    if action not in ("deposit", "withdraw"):
        raise ValueError("action is deposit or withdraw")
    protocol, asset = parse_integration(integration)
    return teller.decide({"action": action, "protocol": protocol, "asset": asset, "amount": amount})
