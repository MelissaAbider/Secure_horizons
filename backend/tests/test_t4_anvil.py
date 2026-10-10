"""T4-25: R1 critical on a seeded anvil chain with Web3Executor (TASKS.md T4).

Skipped while the chain is not there: web3 or backend.chain missing, deployments/local.json missing,
RPC unreachable, or vault not seeded. Run after `make chain && make deploy && make seed`.
"""
import subprocess
from datetime import datetime, timezone

import pytest

from backend import settings
from backend.models import PositionSnapshot, ReserveSnapshot, Snapshot, TokenSnapshot, VaultStatus
from backend.tests.test_t4_fixtures import FakeStore, make_alert

DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}


def _chain_or_skip():
    try:
        from backend import chain
    except ImportError as e:
        pytest.skip(f"backend.chain or web3 not available: {e}")
    if not (settings.ROOT / "deployments" / "local.json").exists():
        pytest.skip("deployments/local.json missing (make chain && make deploy)")
    try:
        chain.w3().eth.block_number
        dep = chain.load_deployment()
        vault = chain.vault()
        supplied = chain.lending("lend-eth").functions.getUserSupplied(vault.address, dep["assets"]["WETH"]).call()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"anvil unreachable: {e}")
    if supplied == 0:
        pytest.skip("vault not seeded (make seed)")
    return chain


def _snapshot_from_chain(chain) -> Snapshot:
    dep = chain.load_deployment()
    by_address = {addr.lower(): sym for sym, addr in dep["assets"].items()}
    prices = {sym: chain.oracle().functions.getPriceE8(addr).call() / 1e8 for sym, addr in dep["assets"].items()}
    vault = chain.vault()
    reserves, positions = [], []
    for lending in dep["lending"]:
        market = chain.lending(lending["id"])
        for r in market.functions.getReservesData().call():
            sym = by_address[r[0].lower()]
            reserves.append(ReserveSnapshot(
                deployment_id=lending["id"], asset=sym, asset_address=r[0], decimals=DECIMALS[sym],
                total_supplied=str(r[1]), total_borrowed=str(r[2]), available_liquidity=str(r[3]),
                total_collateral=str(r[7]), utilization_bps=r[4], supply_apy_bps=r[5], borrow_apy_bps=r[6],
                ltv_bps=r[8], borrowable=r[9], frozen=r[10], paused=r[11], price_usd=prices[sym],
            ))
            supplied = market.functions.getUserSupplied(vault.address, r[0]).call()
            if supplied:
                withdrawable = min(supplied, r[3])
                unit = 10 ** DECIMALS[sym]
                positions.append(PositionSnapshot(
                    wallet=vault.address, deployment_id=lending["id"], asset=sym, supplied=str(supplied),
                    withdrawable_now=str(withdrawable), withdrawable_ratio_bps=withdrawable * 10000 // supplied,
                    value_usd=supplied / unit * prices[sym], withdrawable_usd=withdrawable / unit * prices[sym],
                ))
    block = chain.w3().eth.get_block("latest")
    return Snapshot(
        network="local", chain_id=31337, block_number=block["number"],
        block_time=datetime.fromtimestamp(block["timestamp"], tz=timezone.utc), source="live",
        reserves=reserves, positions=positions,
        tokens=[TokenSnapshot(symbol=s, address=a, decimals=DECIMALS[s], total_supply="0", price_usd=prices[s])
                for s, a in dep["assets"].items()],
        vault=VaultStatus(address=vault.address, deposits_paused=vault.functions.depositsPaused().call()),
    )


def test_critical_on_anvil(monkeypatch):
    chain = _chain_or_skip()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api import response
    from backend.executor import Web3Executor, get_executor
    from backend.responder import Responder

    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    get_executor.cache_clear()
    dep = chain.load_deployment()
    vault = chain.vault()
    usdc_before = chain.token("USDC").functions.balanceOf(vault.address).call()
    weth_before = chain.token("WETH").functions.balanceOf(vault.address).call()

    snap = _snapshot_from_chain(chain)
    alert = make_alert("R1_BACKING_DROP", "critical", snap, asset="rsETH",
                       exposure_usd=sum(p.value_usd for p in snap.positions))
    store = FakeStore()
    (d,) = Responder(store, Web3Executor()).handle([alert], snap)

    assert vault.functions.depositsPaused().call() is True
    assert chain.token("USDC").functions.balanceOf(vault.address).call() - usdc_before == 700000000000
    assert chain.token("WETH").functions.balanceOf(vault.address).call() - weth_before == 250000000000000000000
    withdrawals = [a for a in d.actions if a.type == "EMERGENCY_WITHDRAW"]
    assert len(withdrawals) == 4
    assert all(a.status == "executed" and a.tx_hash.startswith("0x") and len(a.tx_hash) == 66 for a in withdrawals)
    assert chain.registry().functions.anchoredAt(bytes.fromhex(d.record_hash[2:])).call() > 0

    done = subprocess.run(["make", "-f", "mk/t4.mk", "verify", f"ID={d.id}"], cwd=settings.ROOT,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "MATCH" in done.stdout

    app = FastAPI()
    app.include_router(response.router, prefix="/api")
    app.dependency_overrides[response.get_store] = lambda: store
    index = next(i for i, a in enumerate(d.actions) if a.type == "UNPAUSE_DEPOSITS")
    resp = TestClient(app).post(f"/api/decisions/{d.id}/approve",
                                json={"action_index": index, "approver": "treasury-signer-1", "approve": True})
    assert resp.status_code == 200, resp.text
    assert vault.functions.depositsPaused().call() is False
    assert dep["network"] == "local"
    get_executor.cache_clear()
