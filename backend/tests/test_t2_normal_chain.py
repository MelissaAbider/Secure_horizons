"""T2 normal traffic on a local anvil chain (TASKS.md T2, tests T2-40 and T2-41).

Needs NETWORK=local, anvil (or make chain) and NETWORK=local make deploy. The chain is put back as it was afterwards.
"""
import io
import json

import pytest

from backend import chain, settings
from backend.models import RunRecord
from scenario.common import DEPLOYMENTS, Emitter, reserve, units
from scenario.normal import run_normal
from scenario.params import normal_params
from scenario.seed import run_seed
from scenario.testing import local_chain_ready, snapshot

pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="NETWORK=local, anvil and make deploy required")


@pytest.fixture(scope="module")
def normal_run(tmp_path_factory):
    path = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as mp, snapshot():
        mp.setattr(settings, "DATA_DIR", path)
        run_seed()
        stream = io.StringIO()
        rec = run_normal(normal_params(0, seed=7, ticks=60, tick_s=0), "RUN-test-normal-7",
                         Emitter("RUN-test-normal-7", json_mode=True, stream=stream))
        lines = [json.loads(line) for line in stream.getvalue().splitlines()]
        yield {"rec": rec, "lines": lines, "data": path, "rseth_supply": chain.token("rsETH").functions.totalSupply().call(),
               "backing": chain.bridge().functions.backingRatioBps().call(),
               "forged": len(chain.bridge().events.Released().get_logs(from_block=rec.start_block,
                                                                       argument_filters={"sourceVerified": False}))}


def test_normal_safe(normal_run):
    rec = normal_run["rec"]
    for block in range(rec.start_block, rec.end_block + 1):
        for dep in DEPLOYMENTS:
            for sym in ("USDC", "WETH"):
                assert reserve(dep, sym, block)["utilization_bps"] <= 8500, (block, dep, sym)
    assert normal_run["forged"] == 0
    assert normal_run["backing"] == 10_000
    assert normal_run["rseth_supply"] == units(1400, "rsETH")


def test_normal_run_record(normal_run):
    saved = RunRecord.model_validate_json((normal_run["data"] / "runs" / "RUN-test-normal-7.json").read_text())
    assert saved.label == "normal" and saved.attack_start_block is None and saved.phase_blocks == {}
    assert set(saved.treasury_supplied_at_start) == {"lend-eth:WETH", "lend-eth:USDC", "lend-avax:WETH", "lend-avax:USDC"}
    ok = {d["step"] for d in normal_run["lines"] if d["status"] == "ok"}
    assert {"bridge_deposit", "large_deposit"} <= ok
    assert sum(d["step"] in ("supply", "withdraw", "borrow", "repay") for d in normal_run["lines"]) >= 20
