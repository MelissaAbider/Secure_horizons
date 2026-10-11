
import pytest

from backend import rules
from backend.engine import Engine
from backend.tests.test_t3_hardening import advance, collateral_window, reserve, token
from backend.tests.test_t3_rules import MemStore, load_series


@pytest.fixture
def healthy():
    return load_series("snapshots_normal.jsonl")[0].model_copy(deep=True)


def test_bridge_mismatch_alone_is_critical_in_live_mode_when_treasury_exposed(healthy):
    healthy.source = "live"
    token(healthy).bridge_destination_nonce += 1
    r1 = next(a for a in rules.evaluate_all([healthy], rules.load_rules()) if a.rule_id == "R1_BRIDGE_INVARIANT")
    assert r1.severity == "critical"
    assert r1.metrics["evidence_status"] == "unverified"
    assert r1.exposure_usd == 1_325_000.0


def test_live_mismatch_without_exposed_collateral_markets_is_high(healthy):
    healthy.source = "live"
    token(healthy).bridge_destination_nonce += 1
    for r in healthy.reserves:
        if r.asset == "rsETH":
            r.ltv_bps = 0
            r.total_collateral = "0"
    r1 = next(a for a in rules.evaluate_all([healthy], rules.load_rules()) if a.rule_id == "R1_BRIDGE_INVARIANT")
    assert r1.severity == "high"


def test_live_collateral_surge_correlated_with_bridge_mismatch_escalates(healthy):
    window = collateral_window(healthy, 5900 * 10**18)
    for s in window:
        s.source = "live"
    token(window[-1]).bridge_destination_nonce += 1
    r2 = next(a for a in rules.evaluate_r2(window, rules.load_rules()))
    assert r2.severity == "critical"
    assert r2.metrics["bridge_correlated"] == "true"


def test_collateral_surge_still_fires_after_bridge_mismatch_leaves_window(healthy):
    first = healthy.model_copy(deep=True)
    token(first).bridge_destination_nonce += 1
    engine = Engine(MemStore())
    engine.process(first)
    second = advance(first)
    engine.process(second)
    third = advance(second)
    reserve(third, "rsETH").total_collateral = str(5900 * 10**18)
    alerts = engine.process(third)
    r2 = next(a for a in alerts if a.rule_id == "R2_COLLATERAL_SURGE")
    assert r2.severity == "critical"


def test_borrow_against_rseth_after_mismatch_raises_liquidity_rule_early(healthy):
    first = healthy.model_copy(deep=True)
    token(first).bridge_destination_nonce += 1
    second = advance(first)
    r = reserve(second)
    borrowed = int(r.total_borrowed) + 150 * 10**18
    r.total_borrowed = str(borrowed)
    r.available_liquidity = str(int(r.total_supplied) - borrowed)
    alerts = rules.evaluate_r3([first, second], rules.load_rules())
    assert alerts and alerts[0].severity in {"high", "critical"}
    assert "bridge" in alerts[0].metrics["trigger"]


def test_aggregate_risk_is_critical_when_bridge_breaks_and_exposure_exists(healthy):
    healthy.source = "live"
    token(healthy).bridge_destination_nonce += 1
    report = rules.evaluate_snapshot([healthy], rules.load_rules())
    assert max(a.severity for a in report.alerts) == "critical"


def test_recovery_of_bridge_counters_does_not_clear_latched_r1_alone(healthy):
    first = healthy.model_copy(deep=True)
    token(first).bridge_destination_nonce += 1
    engine = Engine(MemStore())
    assert engine.process(first)
    second = advance(first)
    token(second).bridge_destination_nonce = token(second).bridge_source_nonce
    engine.process(second)
    assert ("R1_BRIDGE_INVARIANT", None, "rsETH") in engine.latch.active()
    assert engine.last_evaluation.issues


def test_bridge_mismatch_is_pinned_until_signers_clear(healthy):
    first = healthy.model_copy(deep=True)
    token(first).bridge_destination_nonce += 1
    engine = Engine(MemStore())
    engine.process(first)
    for i in range(1, 25):
        s = advance(first, 2 * i)
        token(s).bridge_destination_nonce = token(s).bridge_source_nonce
        engine.process(s)
    assert ("R1_BRIDGE_INVARIANT", None, "rsETH") in engine.latch.active()
