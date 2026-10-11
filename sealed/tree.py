"""Operations, leaves and the Merkle tree of the sealed list (T10). Pure functions, no chain access.

Same encoding as contracts/src/SealedListModule.sol:
    leaf = keccak256(keccak256(abi.encode(target, selector, words, pinMask, keccak256(pinned words))))
Pairs are hashed sorted (OpenZeppelin MerkleProof), leaves are sorted, an odd node is carried up unchanged.
Tooling rule: every address argument is pinned, amounts stay free. So an operation is "this function, on this
contract, for this asset, towards this recipient", for any amount.

python -m sealed.tree <sealed/deployments/NETWORK.json>   recomputes the root of a published list
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from eth_abi import encode
from eth_utils import keccak, to_checksum_address

FREE = None  # an unpinned argument (an amount)


def arg_types(signature: str) -> list[str]:
    inner = signature[signature.index("(") + 1:-1]
    return inner.split(",") if inner else []


def selector(signature: str) -> bytes:
    return keccak(text=signature)[:4]


def pin_mask(signature: str) -> int:
    """Bit i pins argument i: every address argument, never an amount."""
    return sum(1 << i for i, t in enumerate(arg_types(signature)) if t == "address")


def calldata(signature: str, values: Sequence[Any]) -> bytes:
    types = arg_types(signature)
    return selector(signature) + encode(types, [0 if v is FREE else v for v in values])


def leaf_of(target: str, data: bytes, mask: int) -> bytes:
    """Mirror of SealedListModule.leafOf."""
    if len(data) < 4 or (len(data) - 4) % 32:
        raise ValueError("calldata must be a selector and 32-byte words")
    words = (len(data) - 4) // 32
    if mask >> words:
        raise ValueError("pin mask points past the last argument")
    pinned = b"".join(data[4 + 32 * i:36 + 32 * i] for i in range(words) if mask >> i & 1)
    inner = keccak(encode(["address", "bytes4", "uint256", "uint256", "bytes32"],
                          [to_checksum_address(target), data[:4], words, mask, keccak(pinned)]))
    return keccak(inner)


@dataclass(frozen=True)
class Operation:
    """One allowed operation: FREE marks an argument the operator may choose (the amount)."""

    label: str
    target: str
    signature: str
    args: tuple

    @property
    def mask(self) -> int:
        return pin_mask(self.signature)

    @property
    def leaf(self) -> bytes:
        return leaf_of(self.target, calldata(self.signature, self.args), self.mask)

    def to_json(self) -> dict[str, Any]:
        return {"label": self.label, "target": self.target, "signature": self.signature,
                "args": ["*" if a is FREE else a for a in self.args], "pin_mask": self.mask,
                "leaf": "0x" + self.leaf.hex()}


def integration_operations(protocol_id: str, market: str, asset: str, token: str, safe: str) -> list[Operation]:
    """What ticking one integration (a protocol for one asset) adds to the list: approve, deposit, withdraw back to
    the Safe. The market, the token and the recipient are pinned; amounts stay free."""
    market, token, safe = (to_checksum_address(x) for x in (market, token, safe))
    return [
        Operation(f"Approve {asset} for {protocol_id}", token, "approve(address,uint256)", (market, FREE)),
        Operation(f"Deposit {asset} on {protocol_id}", market, "supply(address,uint256,address)", (token, FREE, safe)),
        Operation(f"Withdraw {asset} from {protocol_id} to the Safe", market, "withdraw(address,uint256,address)",
                  (token, FREE, safe)),
    ]


def protocol_operations(protocol_id: str, market: str, usdc: str, safe: str) -> list[Operation]:
    """The USDC integration of a protocol (the first version of the list)."""
    return integration_operations(protocol_id, market, "USDC", usdc, safe)


def hash_pair(a: bytes, b: bytes) -> bytes:
    return keccak(min(a, b) + max(a, b))


class MerkleTree:
    def __init__(self, leaves: Sequence[bytes]):
        if not leaves:
            raise ValueError("an empty list has no root (seal 0x00…00 to revoke everything)")
        layer = sorted(set(leaves))
        self.layers = [layer]
        while len(layer) > 1:
            layer = [hash_pair(layer[i], layer[i + 1]) if i + 1 < len(layer) else layer[i]
                     for i in range(0, len(layer), 2)]
            self.layers.append(layer)

    @property
    def root(self) -> bytes:
        return self.layers[-1][0]

    def __contains__(self, leaf: bytes) -> bool:
        return leaf in self.layers[0]

    def proof(self, leaf: bytes) -> list[bytes]:
        index = self.layers[0].index(leaf)
        path = []
        for layer in self.layers[:-1]:
            if index ^ 1 < len(layer):
                path.append(layer[index ^ 1])
            index //= 2
        return path


def process_proof(proof: Sequence[bytes], leaf: bytes) -> bytes:
    """Mirror of SealedListModule.processProof: the root an operation lands on."""
    node = leaf
    for sibling in proof:
        node = hash_pair(node, sibling)
    return node


def operations_from_json(leaves: list[dict[str, Any]]) -> list[Operation]:
    return [Operation(x["label"], x["target"], x["signature"], tuple(FREE if a == "*" else a for a in x["args"]))
            for x in leaves]


def check_published(sealed: dict[str, Any]) -> Optional[str]:
    """None when every published operation hashes to its leaf and the leaves rebuild the published root."""
    ops = operations_from_json(sealed["leaves"])
    for op, entry in zip(ops, sealed["leaves"]):
        if "0x" + op.leaf.hex() != entry["leaf"]:
            return f"leaf mismatch for {op.label!r}"
    root = "0x" + MerkleTree([op.leaf for op in ops]).root.hex()
    return None if root == sealed["root"] else f"root mismatch: rebuilt {root}, published {sealed['root']}"


if __name__ == "__main__":
    state = json.loads(open(sys.argv[1], encoding="utf-8").read())
    problem = check_published(state["sealed"])
    print(problem or f"OK: {len(state['sealed']['leaves'])} operations rebuild the root {state['sealed']['root']}")
    sys.exit(1 if problem else 0)
