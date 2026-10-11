"""The teller window, platform side (T10). The agent proposes, the platform checks, the Safe executes.

decide(proposal) turns an agent proposal (data, no key) into contract calls, looks each call up in the sealed list
and submits it with the operator key: module.execute(target, data, pinMask, proof). A call that is not in the list
is refused here, before any transaction (reason NOT_IN_SEALED_LIST). With force=True (demo of a compromised
platform) it is sent anyway, with the neighbors of a real operation: the module recomputes the root, lands
elsewhere and reverts. Every decision, refusals included, is appended to data/runtime/<network>/sealed_decisions.jsonl.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from eth_abi import decode
from eth_utils import keccak, to_checksum_address

from backend import chain, settings
from sealed import safe as S
from sealed.tree import MerkleTree, calldata, leaf_of, pin_mask, process_proof

FORCED_GAS = 150_000  # a refused call reverts early; a fixed limit lets it be mined (and seen) as failed
MAX_UINT = 2**256 - 1  # amount "max": the market withdraws min(position, liquidity)


@dataclass(frozen=True)
class Call:
    label: str
    target: str
    signature: str
    values: tuple

    @property
    def data(self) -> bytes:
        return calldata(self.signature, self.values)

    @property
    def mask(self) -> int:
        return pin_mask(self.signature)

    @property
    def leaf(self) -> bytes:
        return leaf_of(self.target, self.data, self.mask)


def _market(protocol: str, dep: dict[str, Any]) -> str:
    markets = {x["id"]: x["address"] for x in dep["lending"]}
    return to_checksum_address(markets.get(protocol, protocol))  # an id we know, or a raw address (unknown protocol)


def encode(proposal: dict[str, Any], dep: dict[str, Any], safe: str) -> list[Call]:
    """Faithful encoding: the platform does not fix a proposal, the sealed list decides."""
    asset = proposal.get("asset", "USDC")
    token = to_checksum_address(dep["assets"][asset])
    decimals = chain.token(asset).functions.decimals().call()
    amount = MAX_UINT if proposal["amount"] == "max" else int(Decimal(str(proposal["amount"])) * 10**decimals)
    to = to_checksum_address(proposal.get("to") or safe)
    elsewhere = "" if to == to_checksum_address(safe) else f" for {to}"
    action = proposal["action"]
    if action == "deposit":
        market, name = _market(proposal["protocol"], dep), proposal["protocol"]
        return [Call(f"approve {asset} for {name}", token, "approve(address,uint256)", (market, amount)),
                Call(f"supply {asset} on {name}{elsewhere}", market, "supply(address,uint256,address)", (token, amount, to))]
    if action == "withdraw":
        market, name = _market(proposal["protocol"], dep), proposal["protocol"]
        return [Call(f"withdraw {asset} from {name}{elsewhere}", market, "withdraw(address,uint256,address)",
                     (token, amount, to))]
    if action == "transfer":
        return [Call(f"transfer {asset} to {to}", token, "transfer(address,uint256)", (to, amount))]
    raise ValueError(f"unknown action {action!r}")


def sealed_tree(state: dict[str, Any]) -> MerkleTree:
    if not state.get("sealed"):
        raise RuntimeError("nothing sealed yet: make seal PROTOCOLS=lend-avax")
    return MerkleTree([bytes.fromhex(x["leaf"][2:]) for x in state["sealed"]["leaves"]])


def decode_error(data: str, abi: list[dict[str, Any]]) -> dict[str, Any]:
    raw = bytes.fromhex(data[2:] if data.startswith("0x") else data)
    for item in abi:
        if item.get("type") != "error":
            continue
        types = [i["type"] for i in item["inputs"]]
        if keccak(text=f"{item['name']}({','.join(types)})")[:4] == raw[:4]:
            values = decode(types, raw[4:])
            return {"error": item["name"], **{i["name"]: ("0x" + v.hex() if isinstance(v, bytes) else v)
                                              for i, v in zip(item["inputs"], values)}}
    return {"error": "unknown", "data": "0x" + raw.hex()}


def _send_unchecked(fn, sender, gas: int) -> dict[str, Any]:
    """Send without the gas estimate (which would refuse a reverting call): the revert is mined, with no effect."""
    client = chain.w3()
    tx = fn.build_transaction({"from": sender.address, "nonce": client.eth.get_transaction_count(sender.address, "pending"),
                               "gas": gas, "chainId": settings.CHAIN_ID})
    tx_hash = client.eth.send_raw_transaction(sender.sign_transaction(tx).raw_transaction)
    receipt = client.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return {"tx_hash": "0x" + bytes(tx_hash).hex(), "status": int(receipt["status"]), "block_number": int(receipt["blockNumber"])}


def force_through(call: Call, tree: MerkleTree, state: dict[str, Any]) -> dict[str, Any]:
    """Compromised-platform drill: submit a refused call with the proof of a real operation."""
    from web3.exceptions import ContractCustomError

    module = S.contract("SealedListModule", state["module"])
    operator = S.operator_account()
    same_function = [bytes.fromhex(x["leaf"][2:]) for x in state["sealed"]["leaves"]
                     if x["signature"] == call.signature] or [tree.layers[0][0]]
    neighbors = tree.proof(same_function[0])
    fn = module.functions.execute(call.target, call.data, call.mask, neighbors)
    try:
        fn.call({"from": operator.address})
        verdict: dict[str, Any] = {"error": None}
    except ContractCustomError as exc:
        verdict = decode_error(exc.data if isinstance(exc.data, str) else exc.message, module.abi)
    sent = _send_unchecked(fn, operator, FORCED_GAS)
    verdict.update(computed_root="0x" + process_proof(neighbors, call.leaf).hex(), tx_hash=sent["tx_hash"],
                   reverted=sent["status"] == 0, block=sent["block_number"])
    return verdict


def decide(proposal: dict[str, Any], state: Optional[dict[str, Any]] = None, force: bool = False) -> dict[str, Any]:
    state = state or S.load_state()
    tree = sealed_tree(state)
    calls = encode(proposal, chain.load_deployment(), state["safe"])
    record: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "network": settings.NETWORK,
        "proposal": proposal,
        "root": state["root"],
        "calls": [{"label": c.label, "target": c.target, "signature": c.signature,
                   "args": [str(v) for v in c.values], "leaf": "0x" + c.leaf.hex(), "in_list": c.leaf in tree}
                  for c in calls],
        "txs": [],
    }
    missing = [c for c in calls if c.leaf not in tree]
    if missing:
        record.update(verdict="REFUSED", reason="NOT_IN_SEALED_LIST", detail=f"{missing[0].label}: not in the sealed list")
        if force:
            record["on_chain"] = force_through(missing[0], tree, state)
    else:
        module = S.contract("SealedListModule", state["module"])
        operator = S.operator_account()
        for c in calls:
            receipt = chain.send(module.functions.execute(c.target, c.data, c.mask, tree.proof(c.leaf)), operator)
            record["txs"].append(receipt["tx_hash"])
        record.update(verdict="EXECUTED", reason=None)
    path = settings.runtime_dir() / "sealed_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
