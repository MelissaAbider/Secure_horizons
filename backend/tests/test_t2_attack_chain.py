"""T2 attack on a local anvil chain (TASKS.md T2, tests T2-30 to T2-34).

Needs NETWORK=local, anvil (or make chain) and NETWORK=local make deploy. The chain is put back as it was afterwards.
"""
import io
import json
import os
import subprocess
import sys

import pytest

from backend import chain, settings
from backend.models import RunRecord
from scenario.attack import run_attack
from scenario.common import Emitter, asset_address, reserve, units
from scenario.params import attack_params
from scenario.seed import run_seed
from scenario.testing import local_chain_ready, snapshot

pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="NETWORK=local, anvil and make deploy required")
PHASES = ["forged_mint", "collateral_deposit", "first_borrow", "liquidity_zero", "protocol_freeze"]


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as mp, snapshot():
        mp.setattr(settings, "DATA_DIR", path)
        run_seed()
        yield path


@pytest.fixture
def isolated(data_dir):
    with snapshot():
        yield data_dir


def attack(variant="default", seed=0, skip_seed_check=False):
    p = attack_params(variant, seed).with_timing(interval_s=0, warmup_s=0, freeze_delay_s=0)
    stream = io.StringIO()
    rec = run_attack(p, f"RUN-test-{variant}-{seed}", Emitter("RUN-test", json_mode=True, stream=stream),
                     skip_seed_check)
    return rec, [json.loads(line) for line in stream.getvalue().splitlines()]


def test_default_attack_end_state(isolated):
    attack()
    assert chain.bridge().functions.backingRatioBps().call() == 1935
    weth = reserve("lend-eth", "WETH")
    assert (weth["available_liquidity"], weth["total_supplied"], weth["total_borrowed"], weth["utilization_bps"]) == \
        (0, units(1800, "WETH"), units(1800, "WETH"), 10_000)
    attacker = chain.account("attacker").address
    market = chain.lending("lend-eth")
    assert market.functions.getUserBorrowed(attacker, asset_address("WETH")).call() == units(600, "WETH")
    assert chain.token("WETH").functions.balanceOf(attacker).call() == units(600, "WETH")
    assert reserve("lend-eth", "rsETH")["total_collateral"] == units(5900, "rsETH")
    assert reserve("lend-eth", "rsETH")["frozen"] is True and reserve("lend-avax", "rsETH")["frozen"] is False
    assert reserve("lend-avax", "WETH")["available_liquidity"] == units(450, "WETH")


def test_attack_run_record(isolated):
    rec, _ = attack()
    saved = RunRecord.model_validate_json((isolated / "runs" / f"{rec.run_id}.json").read_text())
    assert (saved.label, saved.variant, saved.seed) == ("attack", "default", 0)
    assert list(saved.phase_blocks) == PHASES
    blocks = [saved.phase_blocks[k] for k in PHASES]
    assert blocks == sorted(blocks) and len(set(blocks)) == 5
    assert saved.attack_start_block == saved.phase_blocks["forged_mint"]
    assert saved.start_block < saved.phase_blocks["forged_mint"] and saved.end_block >= saved.phase_blocks["protocol_freeze"]
    assert saved.treasury_supplied_at_start == {
        "lend-eth:WETH": "150000000000000000000", "lend-eth:USDC": "400000000000",
        "lend-avax:WETH": "100000000000000000000", "lend-avax:USDC": "300000000000"}
    assert {"forged_amount", "chunk_weth", "interval_s", "bot_withdrawals"} <= set(saved.params)


def test_attack_json_cli(isolated):
    env = {**os.environ, "NETWORK": "local", "DATA_DIR": str(isolated), "PYTHONUNBUFFERED": "1"}
    out = subprocess.run([sys.executable, "-m", "scenario.attack", "--json", "--interval-s", "0", "--warmup-s", "0",
                          "--freeze-delay-s", "0"], cwd=settings.ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    lines = [json.loads(line) for line in out.stdout.splitlines()]
    steps = [(d["step"], d["status"]) for d in lines]
    assert steps.count(("borrow", "ok")) == 6
    assert steps.count(("bot_withdraw", "ok")) == 2 and steps.count(("bot_withdraw", "blocked")) == 1
    names = [s for s, _ in steps]
    assert names.index("liquidity_zero") < names.index("protocol_freeze") < names.index("done")


def test_attack_after_treasury_exit(isolated):
    owner = chain.account("owner")
    vault = chain.vault()
    chain.send(vault.functions.emergencyWithdraw(chain.lending("lend-eth").address, asset_address("WETH")), owner)
    _, lines = attack(skip_seed_check=True)  # the vault exit is a deliberate change of the reference state
    attacker = chain.account("attacker").address
    assert chain.lending("lend-eth").functions.getUserBorrowed(attacker, asset_address("WETH")).call() == units(550, "WETH")  # 650 available - 100 withdrawn
    withdrawals = [d["status"] for d in lines if d["step"] == "bot_withdraw"]
    assert withdrawals[1] == "blocked"
    assert chain.token("WETH").functions.balanceOf(vault.address).call() == units(150, "WETH")
    assert reserve("lend-eth", "WETH")["available_liquidity"] == 0


def test_usdc_variant(isolated):
    attack("usdc")
    assert reserve("lend-eth", "USDC")["available_liquidity"] == 0
    assert reserve("lend-eth", "WETH")["available_liquidity"] == units(800, "WETH")
