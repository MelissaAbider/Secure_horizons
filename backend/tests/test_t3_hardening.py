from copy import deepcopy
from datetime import timedelta

import pytest

from backend import rules
from backend.engine import Engine
from backend.tests.test_t3_rules import MemStore, load_series


@pytest.fixture
def healthy():
    return load_series("snapshots_normal.jsonl")[0].model_copy(deep=True)


def token(s):
    return next(t for t in s.tokens if t.symbol == "rsETH")


def reserve(s, asset="WETH", deployment="lend-eth"):
    return next(r for r in s.reserves if (r.deployment_id, r.asset) == (deployment, asset))


def position(s):
    return next(p for p in s.positions if (p.deployment_id, p.asset) == ("lend-eth", "WETH"))


def advance(s, blocks=2):
    return s.model_copy(deep=True, update={"block_number": s.block_number + blocks,
                                          "block_time": s.block_time + timedelta(seconds=2 * blocks)})


def alerts(s, rule):
    return [a for a in rules.evaluate_all([s], rules.load_rules()) if a.rule_id == rule]


def collateral_window(healthy, collateral):
    middle = advance(healthy)
    last = advance(middle)
    reserve(last, "rsETH").total_collateral = str(collateral)
    return [healthy, middle, last]


def test_live_nonce_mismatch_is_not_proof_of_fraud(healthy):
    healthy.source = "live"
    token(healthy).bridge_destination_nonce += 1
    result = alerts(healthy, "R1_BRIDGE_INVARIANT")
    assert len(result) == 1
    assert result[0].severity == "warning"
    assert result[0].metrics["evidence_status"] == "unverified"
    assert "without canonical source backing" not in result[0].explanation


def test_live_consistent_counters_still_have_unknown_source_evidence(healthy):
    healthy.source = "live"
    result = rules.evaluate_snapshot([healthy], rules.load_rules())
    assert result.issues
    assert not result.alerts


def test_missing_bridge_evidence_is_not_healthy_and_other_rules_work(healthy):
    token(healthy).bridge_source_locked = None
    reserve(healthy).paused = True
    result = rules.evaluate_snapshot([healthy], rules.load_rules())
    assert "R1_BRIDGE_INVARIANT" in result.unavailable_rules
    assert result.issues
    assert any(a.rule_id == "R4_EXITABILITY_DROP" for a in result.alerts)


def test_gap_only_explanation_does_not_claim_nonce_mismatch(healthy):
    token(healthy).bridge_destination_released = str(1201 * 10**18)
    result = alerts(healthy, "R1_BRIDGE_INVARIANT")[0]
    assert "is ahead" not in result.explanation
    assert result.metrics["evidence_status"] == "synthetic"


def test_nonce_only_explanation_does_not_claim_missing_backing(healthy):
    token(healthy).bridge_destination_nonce += 1
    result = alerts(healthy, "R1_BRIDGE_INVARIANT")[0]
    assert "without canonical source backing" not in result.explanation


def test_unrelated_large_collateral_deposit_is_only_warning(healthy):
    window = collateral_window(healthy, 5900 * 10**18)
    result = rules.evaluate_r2(window, rules.load_rules())
    assert len(result) == 1
    assert result[0].severity == "warning"
    assert result[0].metrics["bridge_correlated"] == "false"


def test_correlated_surge_persists_after_the_first_sample(healthy):
    window = collateral_window(healthy, 5900 * 10**18)
    token(window[-1]).bridge_destination_released = str(6200 * 10**18)
    window.append(advance(window[-1]))
    result = rules.evaluate_r2(window, rules.load_rules())
    assert result[0].severity == "critical"
    assert result[0].metrics["bridge_correlated"] == "true"


def test_zero_baseline_is_not_divided_or_silently_ignored(healthy):
    reserve(healthy, "rsETH").total_collateral = "0"
    window = collateral_window(healthy, 100 * 10**18)
    result = rules.evaluate_r2(window, rules.load_rules())
    assert len(result) == 1
    assert result[0].severity == "warning"
    assert "increase_pct" not in result[0].metrics


def test_unexposed_collateral_does_not_raise_portfolio_alarm(healthy):
    healthy.positions = [p for p in healthy.positions if p.deployment_id != "lend-eth"]
    assert not rules.evaluate_r2(collateral_window(healthy, 5900 * 10**18), rules.load_rules())


@pytest.mark.parametrize("utilization,expected", [(8999, None), (9000, "warning"), (9799, "warning"), (9800, "critical"), (10000, "critical")])
def test_persistent_liquidity_pressure_at_startup(healthy, utilization, expected):
    r = reserve(healthy)
    r.total_supplied = str(10_000 * 10**18)
    r.total_borrowed = str(utilization * 10**18)
    r.available_liquidity = str((10_000 - utilization) * 10**18)
    r.utilization_bps = utilization
    result = alerts(healthy, "R3_LIQUIDITY_DRAIN")
    assert ([a.severity for a in result] or [None]) == [expected]


def test_slow_drain_survives_rolling_baseline(healthy):
    history = []
    for utilization in range(6000, 9851, 50):
        s = advance(healthy, len(history) * 2 + 2)
        r = reserve(s)
        r.total_supplied = str(10_000 * 10**18)
        r.total_borrowed = str(utilization * 10**18)
        r.available_liquidity = str((10_000 - utilization) * 10**18)
        r.utilization_bps = utilization
        history.append(s)
    result = rules.evaluate_r3(history[-2:], rules.load_rules())
    assert result[0].severity == "critical"
    assert result[0].metrics["utilization_bps"] >= 9800


@pytest.mark.parametrize("numerator,denominator,expected", [(4, 5, None), (79999, 100000, "high"), (1, 2, "high"), (49999, 100000, "critical")])
def test_exitability_uses_exact_amounts_not_rounded_ratio(healthy, numerator, denominator, expected):
    p = position(healthy)
    p.supplied = str(denominator * 10**18)
    p.withdrawable_now = str(numerator * 10**18)
    p.withdrawable_ratio_bps = round(numerator / denominator * 10_000)
    r = reserve(healthy)
    r.total_supplied = p.supplied
    r.total_borrowed = str((denominator - numerator) * 10**18)
    r.available_liquidity = p.withdrawable_now
    result = alerts(healthy, "R4_EXITABILITY_DROP")
    assert ([a.severity for a in result] or [None]) == [expected]


def test_paused_reserve_blocks_exit_but_freeze_does_not(healthy):
    reserve(healthy).frozen = True
    assert not alerts(healthy, "R4_EXITABILITY_DROP")
    reserve(healthy).paused = True
    result = alerts(healthy, "R4_EXITABILITY_DROP")
    assert result[0].severity == "critical"
    assert result[0].metrics["withdrawable_now"] == 0


def test_r4_does_not_trust_inflated_withdrawable_field(healthy):
    reserve(healthy).available_liquidity = str(50 * 10**18)
    reserve(healthy).total_borrowed = str(1950 * 10**18)
    assert alerts(healthy, "R4_EXITABILITY_DROP")[0].severity == "critical"


def test_bridge_pause_is_reported_on_startup(healthy):
    token(healthy).bridge_paused = True
    result = alerts(healthy, "R5_CONTAINMENT")
    assert len(result) == 1
    assert result[0].deployment_id is None
    assert result[0].exposure_usd == 1_325_000.0
    assert result[0].metrics["scope"] == "bridge"


def test_freeze_is_persistent_deduplicated_and_rearmed(healthy):
    engine = Engine(MemStore())
    reserve(healthy, "rsETH").frozen = True
    assert any(a.rule_id == "R5_CONTAINMENT" for a in engine.process(healthy))
    second = advance(healthy)
    assert not engine.process(second)
    assert any(a.rule_id == "R5_CONTAINMENT" for a in rules.evaluate_all([second], rules.load_rules()))
    third = advance(second)
    reserve(third, "rsETH").frozen = False
    engine.process(third)
    fourth = advance(third)
    reserve(fourth, "rsETH").frozen = True
    assert any(a.rule_id == "R5_CONTAINMENT" for a in engine.process(fourth))


def test_invalid_snapshot_does_not_poison_window_and_can_be_retried(healthy):
    engine = Engine(MemStore())
    engine.process(healthy)
    bad = advance(healthy)
    reserve(bad).available_liquidity = "-1"
    with pytest.raises(ValueError):
        engine.process(bad)
    assert len(engine.window) == 1
    good = advance(healthy)
    assert engine.process(good) == []
    assert len(engine.window) == 2


@pytest.mark.parametrize("change", ["duplicate", "missing_reserve", "nan", "invalid_amount", "missing_token"])
def test_invalid_snapshots_are_rejected(healthy, change):
    if change == "duplicate":
        healthy.reserves.append(deepcopy(healthy.reserves[0]))
    elif change == "missing_reserve":
        healthy.reserves = [r for r in healthy.reserves if not (r.deployment_id == "lend-eth" and r.asset == "WETH")]
    elif change == "nan":
        position(healthy).value_usd = float("nan")
    elif change == "missing_token":
        healthy.tokens = [t for t in healthy.tokens if t.symbol != "rsETH"]
    else:
        reserve(healthy).available_liquidity = "1.5"
    with pytest.raises(ValueError):
        rules.evaluate_all([healthy], rules.load_rules())


def test_unknown_bridge_sample_does_not_rearm_ongoing_alarm(healthy):
    token(healthy).bridge_destination_nonce += 1
    engine = Engine(MemStore())
    engine.process(healthy)
    missing = advance(healthy)
    token(missing).bridge_source_nonce = None
    engine.process(missing)
    assert not [a for a in engine.process(advance(healthy, 4)) if a.rule_id == "R1_BRIDGE_INVARIANT"]


def test_ordering_and_chain_identity_are_checked(healthy):
    wrong_chain = advance(healthy)
    wrong_chain.chain_id += 1
    with pytest.raises(ValueError):
        rules.evaluate_all([healthy, wrong_chain], rules.load_rules())
    with pytest.raises(ValueError):
        rules.evaluate_all([advance(healthy), healthy], rules.load_rules())


def test_disabled_rules_remain_disabled(healthy):
    token(healthy).bridge_destination_nonce += 1
    reserve(healthy).paused = True
    cfg = rules.load_rules()
    for key, rule in cfg.items():
        if key.startswith("R"):
            rule["enabled"] = False
    assert not rules.evaluate_all([healthy], cfg)


def test_invalid_config_fails_before_monitoring():
    cfg = rules.load_rules()
    cfg["R3_LIQUIDITY_DRAIN"]["critical_drop_pct"] = 10
    with pytest.raises(ValueError):
        Engine(MemStore(), cfg=cfg)


def test_partial_reserve_inventory_is_not_a_recovery(healthy):
    partial = advance(healthy)
    partial.reserves = [r for r in partial.reserves if r.asset != "rsETH"]
    with pytest.raises(ValueError, match="inventory"):
        rules.evaluate_all([healthy, partial], rules.load_rules())


@pytest.mark.parametrize("remaining,severity", [(701, None), (700, "high"), (401, "high"), (400, "critical")])
def test_liquidity_drop_exact_boundaries(healthy, remaining, severity):
    first = healthy.model_copy(deep=True)
    r = reserve(first)
    r.total_supplied = str(2000 * 10**18)
    r.total_borrowed = str(1000 * 10**18)
    r.available_liquidity = str(1000 * 10**18)
    last = advance(first)
    r = reserve(last)
    r.available_liquidity = str(remaining * 10**18)
    r.total_borrowed = str((2000 - remaining) * 10**18)
    result = rules.evaluate_r3([first, last], rules.load_rules())
    assert ([a.severity for a in result] or [None]) == [severity]


@pytest.mark.parametrize("delta,severity", [(449, None), (450, "high"), (1799, "high"), (1800, "critical")])
def test_correlated_collateral_exact_boundaries(healthy, delta, severity):
    window = collateral_window(healthy, (900 + delta) * 10**18)
    token(window[-1]).bridge_destination_nonce += 1
    result = rules.evaluate_r2(window, rules.load_rules())
    assert ([a.severity for a in result] or [None]) == [severity]


def test_rules_are_pure_and_repeatable(healthy):
    inputs = collateral_window(healthy, 5900 * 10**18)
    token(inputs[-1]).bridge_destination_nonce += 1
    before = [s.model_dump() for s in inputs]
    cfg = rules.load_rules()
    config_before = deepcopy(cfg)
    assert rules.evaluate_snapshot(inputs, cfg) == rules.evaluate_snapshot(inputs, cfg)
    assert [s.model_dump() for s in inputs] == before
    assert cfg == config_before


def test_stale_live_snapshot_is_not_processed(healthy):
    healthy.source = "live"
    engine = Engine(MemStore(), clock=lambda: healthy.block_time + timedelta(hours=1))
    with pytest.raises(ValueError, match="stale"):
        engine.process(healthy)
    assert not engine.window
