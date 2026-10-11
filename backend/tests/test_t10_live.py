"""T10 dashboard flow on a local chain: a wallet connects, signs the Safe transactions in the browser (simulated
here with a throwaway key signing the same EIP-712 data), seals WETH and USDC integrations, allocates, and the
monitor follows the Safe. Needs NETWORK=local, anvil, make deploy and make t1-build."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from eth_account import Account

from backend import chain, settings
from scenario.testing import local_chain_ready, snapshot

pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="NETWORK=local, anvil and make deploy required")


@pytest.fixture
def live(tmp_path, monkeypatch):
    from backend import collector
    from sealed import live as L
    from sealed import safe as S

    if not (S.OUT / "SafeL2.sol" / "SafeL2.json").exists():
        pytest.skip("contracts not built (make t1-build)")
    monkeypatch.setattr(S, "STATE_DIR", tmp_path / "sealed")
    monkeypatch.setattr(collector, "SEALED_STATE_DIR", tmp_path / "sealed")
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    with snapshot():
        yield L


def sign(owner, request: dict) -> str:
    return "0x" + bytes(owner.sign_typed_data(full_message=request["typed_data"]).signature).hex()


def test_connect_sign_seal_allocate_and_monitor(live):
    import io

    from backend.collector import build_snapshot
    from scenario.attack import run_attack
    from scenario.common import Emitter
    from scenario.params import attack_params
    from scenario.seed import run_seed

    run_seed(Emitter("RUN-test-seed", json_mode=True, stream=io.StringIO()))
    owner = Account.create()  # the manager's wallet: it only signs, it needs no gas
    status = live.connect(owner.address)
    assert status["connected"] and status["owner"] == owner.address and not status["module_enabled"]
    assert int(status["balances"]["USDC"]) == 1_000_000 * 10**6 and int(status["balances"]["WETH"]) == 500 * 10**18
    assert live.connect(owner.address)["safe"] == status["safe"]  # reconnecting reuses the Safe

    enable = live.prepare("enable_module")
    assert enable["typed_data"]["domain"]["verifyingContract"] == status["safe"]
    assert live.submit(enable, sign(owner, enable))["status"]["module_enabled"]

    request = live.prepare("seal", ["lend-eth:WETH", "lend-avax"])
    with pytest.raises(PermissionError):
        live.submit(request, sign(Account.create(), request))  # anyone else's signature is refused before sending
    sealed = live.submit(request, sign(owner, request))["status"]
    assert sealed["seal_status"] == "sealed" and sealed["root"] == request["root"]
    assert sealed["sealed_integrations"] == ["lend-eth:WETH", "lend-avax:USDC"]

    assert live.allocate("lend-eth:WETH", "deposit", "200")["verdict"] == "EXECUTED"
    assert live.allocate("lend-avax:USDC", "deposit", "300000")["verdict"] == "EXECUTED"
    refused = live.allocate("lend-eth:USDC", "deposit", "1000")
    assert refused["verdict"] == "REFUSED" and not refused["txs"]
    positions = {p["integration"]: int(p["supplied"]) for p in live.status()["positions"]}
    assert positions == {"lend-eth:WETH": 200 * 10**18, "lend-avax:USDC": 300_000 * 10**6}

    snap = build_snapshot(chain.w3().eth.block_number)
    assert snap.vault.address == status["safe"]  # the monitor now watches the client's Safe
    assert {(p.deployment_id, p.asset) for p in snap.positions} == {("lend-eth", "WETH"), ("lend-avax", "USDC")}

    # the default attack drains lend-eth WETH: the Safe's position there is caught, its USDC on lend-avax is not
    run_attack(attack_params("default", 0).with_timing(0, 0, 0), "RUN-test-attack",
               Emitter("RUN-test-attack", json_mode=True, stream=io.StringIO()))
    after = {(p.deployment_id, p.asset): p for p in build_snapshot(chain.w3().eth.block_number).positions}
    assert after[("lend-eth", "WETH")].withdrawable_ratio_bps == 0
    assert after[("lend-avax", "USDC")].withdrawable_ratio_bps == 10_000



def test_safe_routes(live):
    from fastapi.testclient import TestClient

    from backend.api import demo
    from backend.main import app
    from backend.models import DemoRun

    client, owner = TestClient(app), Account.create()
    assert client.get("/api/safe").json()["connected"] is False
    st = client.post("/api/safe/connect", json={"owner": owner.address}).json()
    assert st["connected"] and not st["module_enabled"]
    req = client.post("/api/safe/prepare", json={"action": "enable_module"}).json()
    bad = client.post("/api/safe/submit", json={"safe_tx_hash": req["safe_tx_hash"], "signature": sign(Account.create(), req)})
    assert bad.status_code == 400 and "not by the Safe owner" in bad.json()["detail"]
    ok = client.post("/api/safe/submit", json={"safe_tx_hash": req["safe_tx_hash"], "signature": sign(owner, req)}).json()
    assert ok["status"]["module_enabled"]
    req = client.post("/api/safe/prepare", json={"action": "seal", "integrations": ["lend-eth:WETH"]}).json()
    assert client.post("/api/safe/submit", json={"safe_tx_hash": req["safe_tx_hash"],
                                                 "signature": sign(owner, req)}).json()["status"]["seal_status"] == "sealed"
    done = client.post("/api/safe/allocate", json={"integration": "lend-eth:WETH", "action": "deposit", "amount": "10"}).json()
    assert done["verdict"] == "EXECUTED" and len(done["txs"]) == 2  # approve + supply, both through the module
    demo._RUNS["RUN-busy"] = DemoRun(run_id="RUN-busy", kind="attack", status="running", started_at=datetime.now(timezone.utc))
    try:  # never while a demo run uses the deployer key
        assert client.post("/api/safe/allocate", json={"integration": "lend-eth:WETH", "action": "withdraw", "amount": "max"}).status_code == 409
    finally:
        demo._RUNS.pop("RUN-busy")
