"""T2 parameters (TASKS.md T2, tests T2-01 to T2-05). Pure, no chain."""
from pathlib import Path

import pytest

from scenario.params import attack_params

ROOT = Path(__file__).resolve().parents[2]


def test_default_attack_params():
    p = attack_params("default", 0, "fuji")
    assert (p.forged_amount, p.drain_asset, p.chunk) == (5000, "WETH", 100)
    assert (p.interval_s, p.warmup_s, p.freeze_delay_s) == (8.0, 24.0, 80.0)
    assert p.withdraw_after == (4, 5) and p.bot_withdraw_amount == 100
    assert attack_params("default", 0, "local").interval_s == 1.0


@pytest.mark.parametrize("variant", ["default", "slow", "usdc"])
def test_seeded_params_deterministic_and_in_range(variant):
    chunks = {"default": {50, 100, 150, 200}, "slow": {10, 25, 40}, "usdc": {100_000, 250_000, 400_000}}[variant]
    for seed in range(1, 201):
        p = attack_params(variant, seed, "fuji")
        assert p == attack_params(variant, seed, "fuji")
        assert 3000 <= p.forged_amount <= 8000 and p.forged_amount % 500 == 0
        assert p.chunk in chunks
        assert 1 <= len(p.withdraw_after) <= 3 and len(set(p.withdraw_after)) == len(p.withdraw_after)
        assert all(2 <= i <= 7 for i in p.withdraw_after)
    assert attack_params(variant, 42, "fuji") != attack_params(variant, 43, "fuji")


def test_variants():
    slow = attack_params("slow", 0, "fuji")
    assert (slow.chunk, slow.interval_s) == (25, 24.0)
    usdc = attack_params("usdc", 0, "fuji")
    assert (usdc.drain_asset, usdc.chunk) == ("USDC", 250_000)
    with pytest.raises(ValueError):
        attack_params("foo")


def test_as_params_types():
    params = attack_params("default", 0, "fuji").as_params()
    assert all(isinstance(v, (str, int, float, bool)) for v in params.values())
    assert params["forged_amount"] == 5000 and params["chunk_weth"] == 100 and params["interval_s"] == 8.0
    assert params["bot_withdrawals"] == 2 and params["withdraw_after"] == "4,5"
    usdc = attack_params("usdc", 0, "fuji").as_params()
    assert usdc["chunk_weth"] == 0 and usdc["chunk_usdc"] == 250_000


def test_no_rules_coupling():
    forbidden = ("rules.yaml", "backend.rules", "backend.engine", "backend.config")
    for path in (ROOT / "scenario").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(f in text for f in forbidden), path.name
