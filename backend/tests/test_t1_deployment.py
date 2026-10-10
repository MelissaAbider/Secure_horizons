"""T1: the local deployment matches TASKS.md 2.2 and 2.3. Skipped when no local chain or deployment is available."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend import chain, fixtures, settings

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "deployments" / "local.json"


@pytest.fixture(scope="module")
def deployment() -> dict:
    if settings.NETWORK != "local" or not LOCAL.exists():
        pytest.skip("no local deployment (run make chain, then make deploy)")
    try:
        chain.w3().eth.block_number
    except Exception:
        pytest.skip("local chain not running")
    return json.loads(LOCAL.read_text())


def test_format_and_code(deployment: dict) -> None:
    assert set(deployment) >= {"network", "chain_id", "deployed_at_block", "explorer", "assets", "contracts", "lending", "roles"}
    addresses = list(deployment["assets"].values()) + list(deployment["contracts"].values()) + [x["address"] for x in deployment["lending"]]
    assert len(addresses) == 9
    for addr in addresses:
        assert len(chain.w3().eth.get_code(addr)) > 0, addr
    for name in ("MockERC20", "RsETH", "MockBridge", "MockOracle", "MiniLend", "TreasuryVault", "EvidenceRegistry"):
        assert (ROOT / "abi" / f"{name}.json").exists()


def test_same_addresses_as_fixtures_on_fresh_anvil(deployment: dict) -> None:
    example = fixtures.load("deployments.example.json")
    assert deployment["assets"] == example["assets"]
    assert deployment["contracts"] == example["contracts"]
    assert [x["address"] for x in deployment["lending"]] == [x["address"] for x in example["lending"]]


def test_onchain_configuration(deployment: dict) -> None:
    oracle = chain.oracle()
    assert oracle.functions.getPriceE8(deployment["assets"]["USDC"]).call() == 10**8
    assert oracle.functions.getPriceE8(deployment["assets"]["WETH"]).call() == 2500 * 10**8
    for market in deployment["lending"]:
        reserves = chain.lending(market["id"]).functions.getReservesData().call()
        assert [r[0] for r in reserves] == [deployment["assets"][s] for s in ("USDC", "WETH", "rsETH")]
        assert [r[8] for r in reserves] == [8000, 8000, 7500]
        assert chain.lending(market["id"]).functions.protocolGuardian().call() == deployment["roles"]["protocol_guardian"]
    vault = chain.vault()
    assert vault.functions.owner().call() == deployment["roles"]["owner"]
    assert vault.functions.guardian().call() == deployment["roles"]["guardian"]
    assert chain.bridge().functions.backingRatioBps().call() == 10_000
