"""T10: the sealed list. List tests run everywhere; chain tests need NETWORK=local, anvil, make deploy and make t1-build."""
from __future__ import annotations

import pytest
from eth_utils import keccak, to_checksum_address

from backend import chain, settings
from sealed.tree import (
    MerkleTree, calldata, check_published, leaf_of, pin_mask, process_proof, protocol_operations,
)

USDC = to_checksum_address("0x5fbdb2315678afecb367f032d93f642f64180aa3")
MARKET = to_checksum_address("0x0165878a594ca255338adfa4d48449f69242eb8f")
OTHER_MARKET = to_checksum_address("0x5fc8d32690cc91d4c39d9d3abcbd16989f875707")
SAFE = to_checksum_address("0x98b784472747766da4a294beb06246b7422e34a1")
STRANGER = to_checksum_address("0x9c000000000000000000000000000000000000f1")
SUPPLY = "supply(address,uint256,address)"


def test_addresses_are_pinned_amounts_are_free() -> None:
    assert pin_mask("approve(address,uint256)") == 0b1
    assert pin_mask(SUPPLY) == 0b101
    assert pin_mask("withdraw(address,uint256,address)") == 0b101
    small = leaf_of(MARKET, calldata(SUPPLY, (USDC, 1, SAFE)), 0b101)
    big = leaf_of(MARKET, calldata(SUPPLY, (USDC, 10**30, SAFE)), 0b101)
    elsewhere = leaf_of(MARKET, calldata(SUPPLY, (USDC, 1, STRANGER)), 0b101)
    assert small == big != elsewhere


def test_every_leaf_proves_against_the_root() -> None:
    for n in range(1, 9):  # odd layers carry a node up unchanged
        leaves = [keccak(text=str(i)) for i in range(n)]
        tree = MerkleTree(leaves)
        for leaf in leaves:
            assert process_proof(tree.proof(leaf), leaf) == tree.root


def test_root_ignores_order_and_duplicates() -> None:
    leaves = [op.leaf for op in protocol_operations("lend-avax", MARKET, USDC, SAFE)]
    assert MerkleTree(leaves).root == MerkleTree(list(reversed(leaves)) + leaves[:1]).root


def test_operation_outside_the_list_lands_elsewhere() -> None:
    ops = protocol_operations("lend-avax", MARKET, USDC, SAFE)
    tree = MerkleTree([op.leaf for op in ops])
    forged = leaf_of(USDC, calldata("transfer(address,uint256)", (STRANGER, 500_000 * 10**6)), 0b1)
    assert forged not in tree
    assert process_proof(tree.proof(ops[1].leaf), forged) != tree.root


def test_published_list_rebuilds_its_root() -> None:
    ops = protocol_operations("lend-avax", MARKET, USDC, SAFE)
    sealed = {"root": "0x" + MerkleTree([op.leaf for op in ops]).root.hex(), "leaves": [op.to_json() for op in ops]}
    assert check_published(sealed) is None
    swapped = dict(sealed["leaves"][0], args=[OTHER_MARKET, "*"])  # same leaf hash claimed for another spender
    assert "leaf mismatch" in check_published({**sealed, "leaves": [swapped] + sealed["leaves"][1:]})


# ---------- on a local chain ----------

@pytest.fixture(scope="module")
def deployed() -> dict:
    from sealed import safe as S

    if settings.NETWORK != "local" or not settings.DEPLOYMENTS_FILE.exists():
        pytest.skip("no local deployment (make chain, make deploy)")
    try:
        chain.w3().eth.block_number
    except Exception:
        pytest.skip("local chain not running")
    if not (S.OUT / "SealedListModule.sol" / "SealedListModule.json").exists():
        pytest.skip("contracts not built (make t1-build)")
    from sealed import deploy

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("FORCE", "1")
        assert deploy.main() == 0
    return S.load_state()


def _supplied(state: dict, market: str) -> int:
    return chain.lending(market).functions.getUserSupplied(state["safe"], chain.load_deployment()["assets"]["USDC"]).call()


def test_python_leaf_is_the_module_leaf(deployed: dict) -> None:
    from sealed import safe as S

    dep = chain.load_deployment()
    module = S.contract("SealedListModule", deployed["module"])
    market = next(x["address"] for x in dep["lending"] if x["id"] == "lend-avax")
    for op in protocol_operations("lend-avax", market, dep["assets"]["USDC"], deployed["safe"]):
        assert module.functions.leafOf(op.target, calldata(op.signature, op.args), op.mask).call() == op.leaf


def test_the_list_decides_what_the_safe_does(deployed: dict) -> None:
    from sealed import seal, teller
    from sealed.agent_stub import exits, proposals

    state = seal.seal(["lend-avax"])
    verdicts = {p["id"]: teller.decide(p, state, force=True) for p in proposals()}
    assert [verdicts[i]["verdict"] for i in ("P1", "P2")] == ["EXECUTED", "EXECUTED"]
    for i in ("P3", "P4", "P5", "P6"):
        assert verdicts[i]["verdict"] == "REFUSED" and verdicts[i]["reason"] == "NOT_IN_SEALED_LIST"
        forced = verdicts[i]["on_chain"]
        assert forced["error"] == "NotInSealedList" and forced["reverted"]
        assert forced["sealedRoot"] == state["root"] != forced["computedRoot"] == forced["computed_root"]
    assert _supplied(state, "lend-avax") == 60_000 * 10**6
    assert _supplied(state, "lend-eth") == 0

    state = seal.seal(["lend-avax", "lend-eth"])  # the owners tick lend-eth: new root, new signatures
    assert teller.decide(next(p for p in proposals() if p["id"] == "P6"), state)["verdict"] == "EXECUTED"
    assert _supplied(state, "lend-eth") == 50_000 * 10**6
    for p in exits(["lend-avax", "lend-eth"]):
        assert teller.decide(p, state)["verdict"] == "EXECUTED"
    assert _supplied(state, "lend-avax") == _supplied(state, "lend-eth") == 0


def test_only_the_owners_change_the_seal(deployed: dict) -> None:
    from web3.exceptions import ContractCustomError

    from sealed import safe as S

    module = S.contract("SealedListModule", deployed["module"])
    for who in (S.operator_account(), S.owner_accounts()[0], chain.account("deployer")):
        with pytest.raises(ContractCustomError):
            module.functions.setRoot(b"\x01" * 32).call({"from": who.address})
