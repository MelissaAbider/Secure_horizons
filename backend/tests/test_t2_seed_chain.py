"""T2 seed on a local anvil chain (TASKS.md T2, tests T2-20 to T2-24).

Needs NETWORK=local, anvil (or make chain) and NETWORK=local make deploy. The chain is put back as it was afterwards.
"""
import pytest

from backend import chain, settings
from scenario.common import (
    PreflightError, asset_address, maintenance_flag_path, reserve, roles, treasury_supplied, units,
)
from scenario.seed import detect_seed_state, expected_reserves, run_seed
from scenario.testing import local_chain_ready, snapshot

pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="NETWORK=local, anvil and make deploy required")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp, snapshot():
        mp.setattr(settings, "DATA_DIR", tmp_path_factory.mktemp("data"))
        from_block = chain.w3().eth.block_number
        result = run_seed()
        yield {"result": result, "from_block": from_block}


@pytest.fixture
def isolated(seeded):
    with snapshot():
        yield seeded


def test_seed_matches_contract_table(isolated):
    assert isolated["result"]["status"] in ("seeded", "already_seeded")
    for (dep, sym), (supplied, borrowed, collateral) in expected_reserves().items():
        r = reserve(dep, sym)
        assert (r["total_supplied"], r["total_borrowed"], r["total_collateral"]) == (supplied, borrowed, collateral), (dep, sym)
    assert reserve("lend-eth", "USDC")["total_supplied"] == units(3_000_000, "USDC")  # collateral is a separate balance
    assert chain.token("rsETH").functions.totalSupply().call() == units(1200, "rsETH")
    assert chain.bridge().functions.backingRatioBps().call() == 10_000
    assert treasury_supplied() == {"lend-eth:USDC": str(units(400_000, "USDC")), "lend-eth:WETH": str(units(150, "WETH")),
                                   "lend-avax:USDC": str(units(300_000, "USDC")), "lend-avax:WETH": str(units(100, "WETH"))}
    vault = chain.vault().address
    assert all(chain.token(s).functions.balanceOf(vault).call() == 0 for s in ("USDC", "WETH", "rsETH"))


def test_seed_leaves_prices_guardian_and_flag(isolated):
    oracle = chain.oracle()
    prices = {s: oracle.functions.getPriceE8(asset_address(s)).call() for s in ("USDC", "WETH", "rsETH")}
    assert prices == {"USDC": 10**8, "WETH": 2500 * 10**8, "rsETH": 2500 * 10**8}
    first, last = isolated["from_block"] + 1, chain.w3().eth.block_number
    if last >= first:  # no block at all when the chain was already seeded
        assert len(oracle.events.PriceUpdated().get_logs(from_block=first, to_block=last)) == 0
    assert chain.vault().functions.guardian().call() == roles()["guardian"]
    assert chain.vault().functions.depositsPaused().call() is False
    assert not maintenance_flag_path().exists()


def test_seed_idempotent(isolated):
    w3 = chain.w3()
    accounts = [chain.account(r).address for r in ("deployer", "owner")] + [b.address for b in chain.bot_accounts()]
    nonces = [w3.eth.get_transaction_count(a) for a in accounts]
    assert run_seed() == {"status": "already_seeded"}
    assert [w3.eth.get_transaction_count(a) for a in accounts] == nonces


def test_partial_state_rejected(isolated):
    lender = chain.bot_accounts()[0]
    market = chain.lending("lend-eth")
    chain.send(market.functions.supply(asset_address("WETH"), units(1, "WETH"), lender.address), lender)
    assert detect_seed_state() == "partial"
    with pytest.raises(PreflightError):
        run_seed()


def test_bot_balances(isolated):
    bots = [b.address for b in chain.bot_accounts()]
    weth, usdc, rseth = (chain.token(s).functions for s in ("WETH", "USDC", "rsETH"))
    assert (weth.balanceOf(bots[0]).call(), usdc.balanceOf(bots[0]).call()) == (units(500, "WETH"), units(1_000_000, "USDC"))
    assert (weth.balanceOf(bots[1]).call(), usdc.balanceOf(bots[1]).call()) == (units(1750, "WETH"), units(2_900_000, "USDC"))
    assert rseth.balanceOf(bots[1]).call() == 0
    assert weth.balanceOf(bots[2]).call() == units(500, "WETH")
