"""R7 LLM agent and three-layer consensus (T3). The LLM is always a stub here: no network, no key."""
import json
import time

import pytest

from backend import consensus, rules, settings
from backend.agent_monitor import AgentMonitor, RULE_ID, parse_verdict, prompt_hash
from backend.engine import Engine, STATUS
from backend.models import Alert
from backend.tests.test_t3_hardening import advance, reserve, token
from backend.tests.test_t3_rules import MemStore, load_series


def cfg():
    return rules.load_rules()


def verdict(severity="high", phases=(1, 2), dep="lend-eth", asset="rsETH", **extra):
    return json.dumps({"severity": severity, "phases": list(phases), "deployment_id": dep, "asset": asset,
                       "reasoning": "bridge release ahead of source nonce, rsETH collateral x10 in 3 blocks", "evidence": {"nonce_gap": "1"}, **extra})


def agent(answer, **kw):
    calls = []

    def call(system, user):
        calls.append((system, user))
        return answer() if callable(answer) else answer
    a = AgentMonitor(cfg(), call=call, min_interval_s=0, **kw)
    a.calls = calls
    return a


@pytest.fixture
def healthy():
    return load_series("snapshots_normal.jsonl")[0].model_copy(deep=True)


@pytest.fixture(autouse=True)
def _no_bedrock(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")


# ---------- agent guardrails ----------

def test_disabled_without_model_id_reports_unavailable_not_safe(healthy):
    a = AgentMonitor(cfg())
    alerts, issues = a.evaluate([healthy])
    assert alerts == [] and issues and "disabled" in issues[0]
    assert a.status.available is False


def test_valid_verdict_becomes_capped_alert_with_prompt_hash(healthy):
    a = agent(verdict())
    alerts, issues = a.evaluate([healthy])
    assert not issues and len(alerts) == 1
    al = alerts[0]
    assert al.rule_id == RULE_ID and al.severity == "high" and al.deployment_id == "lend-eth" and al.asset == "rsETH"
    assert al.rules_version.startswith(cfg()["_version"]) and "prompt:" in al.rules_version
    assert al.metrics["layer"] == "llm" and al.metrics["evidence.nonce_gap"] == "1"
    assert al.exposure_usd > 0


def test_critical_from_llm_is_rejected_by_schema(healthy):
    a = agent(verdict(severity="critical"))
    alerts, issues = a.evaluate([healthy])
    assert alerts == [] and a.status.rejected == 1 and "rejected" in issues[0]


def test_hallucinated_deployment_or_asset_is_rejected(healthy):
    for bad in (verdict(dep="lend-mars"), verdict(asset="DOGE")):
        a = agent(bad)
        alerts, issues = a.evaluate([healthy])
        assert alerts == [] and a.status.rejected == 1


def test_prose_or_broken_json_is_rejected(healthy):
    for bad in ("I think this is fine.", "{not json", verdict(phases=[9]), json.dumps({"severity": "high", "phases": [], "reasoning": "x"})):
        a = agent(bad)
        assert a.evaluate([healthy])[0] == []


def test_none_verdict_yields_no_alert_and_no_issue(healthy):
    a = agent(verdict(severity="none", phases=[], dep=None, asset=None))
    assert a.evaluate([healthy]) == ([], [])


def test_provider_error_and_timeout_never_raise(healthy):
    def boom(s, u):
        raise RuntimeError("bedrock down")
    a = AgentMonitor(cfg(), call=boom, min_interval_s=0)
    alerts, issues = a.evaluate([healthy])
    assert alerts == [] and "provider error" in issues[0] and a.status.available is False

    def slow(s, u):
        time.sleep(0.5)
        return verdict()
    a = AgentMonitor(cfg(), call=slow, min_interval_s=0, timeout_s=0.05)
    alerts, issues = a.evaluate([healthy])
    assert alerts == [] and "timeout" in issues[0]
    a.close()


def test_rate_limit_and_cache(healthy):
    now = [100.0]
    a = AgentMonitor(cfg(), call=lambda s, u: verdict(), clock=lambda: now[0], min_interval_s=1.0)
    assert a.evaluate([healthy])[0]
    assert a.evaluate([healthy])[1] == [] and a.status.cache_hits == 1  # same window -> cache, no call
    nxt = advance(healthy)
    assert "rate limited" in a.evaluate([healthy, nxt])[1][0]
    now[0] += 1.0
    assert a.evaluate([healthy, nxt])[0]
    assert a.status.calls == 2


def test_prompt_contains_no_secret_and_is_hashed():
    text = (settings.CONFIG_DIR / "agent_prompt.md").read_text(encoding="utf-8")
    assert "critical" in text and "never output \"critical\"" in text.lower().replace("“", '"').replace("”", '"') or "never output" in text
    assert prompt_hash().startswith("sha256:")
    assert not any(k in text for k in ("PK", "0x", "secret", "token"))


def test_user_payload_excludes_addresses(healthy):
    a = agent(verdict())
    a.evaluate([healthy])
    _, user = a.calls[0]
    assert healthy.vault.address.lower() not in user.lower()
    assert all(t.address.lower() not in user.lower() for t in healthy.tokens)


# ---------- consensus ----------

def mk(rule_id, severity, dep="lend-eth", asset="WETH"):
    return Alert(id=f"ALT-local-1-{rule_id}-{dep}-{asset}", rule_id=rule_id, severity=severity, network="local", deployment_id=dep, asset=asset,
                 block_number=1, block_time="2026-01-01T00:00:00Z", detected_at="2026-01-01T00:00:00Z", title="t", explanation="e",
                 metrics={}, exposure_usd=1.0, rules_version="v")


def test_rules_pass_through_including_critical():
    r = consensus.resolve([mk("R1_BRIDGE_INVARIANT", "critical", None, "rsETH")])
    assert r.forwarded[0].severity == "critical" and r.agreement == "single" and r.layers_alerting == {"rules"}


def test_llm_alone_is_downgraded_to_warning():
    r = consensus.resolve([mk("R7_AGENT_LLM", "high")])
    assert r.forwarded[0].severity == "warning" and r.downgraded and "uncorroborated" in r.forwarded[0].explanation


def test_llm_corroborated_by_rule_keeps_high_never_critical():
    r = consensus.resolve([mk("R3_LIQUIDITY_DRAIN", "high"), mk("R7_AGENT_LLM", "critical")])
    sev = {a.rule_id: a.severity for a in r.forwarded}
    assert sev["R7_AGENT_LLM"] == "high" and sev["R3_LIQUIDITY_DRAIN"] == "high"
    assert r.corroborated and r.agreement == "partial"


def test_ml_and_llm_agree_without_rules_is_high():
    r = consensus.resolve([mk("R6_ML_ANOMALY", "high"), mk("R7_AGENT_LLM", "high")])
    assert all(a.severity == "high" for a in r.forwarded) and r.agreement == "partial" and len(r.corroborated) == 2


def test_global_rule_corroborates_scoped_llm_but_other_deployment_does_not():
    r = consensus.resolve([mk("R1_BRIDGE_INVARIANT", "critical", None, None), mk("R7_AGENT_LLM", "high", "lend-avax", "USDC")])
    assert {a.severity for a in r.forwarded} == {"critical", "high"}
    r = consensus.resolve([mk("R3_LIQUIDITY_DRAIN", "high", "lend-eth", "WETH"), mk("R7_AGENT_LLM", "high", "lend-avax", "USDC")])
    assert [a.severity for a in r.forwarded if a.rule_id == "R7_AGENT_LLM"] == ["warning"]


def test_three_layers_full_agreement():
    r = consensus.resolve([mk("R2_COLLATERAL_SURGE", "high", "lend-eth", "rsETH"), mk("R6_ML_ANOMALY", "high", "lend-eth", "rsETH"), mk("R7_AGENT_LLM", "high", "lend-eth", "rsETH")])
    assert r.agreement == "full" and r.max_severity == "high"


# ---------- engine integration ----------

def test_engine_runs_rules_even_when_agent_explodes(healthy):
    def boom(s, u):
        raise RuntimeError("x")
    engine = Engine(MemStore(), agent=AgentMonitor(cfg(), call=boom, min_interval_s=0))
    token(healthy).bridge_destination_nonce += 1
    new = engine.process(healthy)
    assert [a.rule_id for a in new] == ["R1_BRIDGE_INVARIANT"]
    assert any("R7" in i for i in STATUS.data_issues) and STATUS.agent_available is False


def test_engine_downgrades_lone_agent_alert_and_latches_it(healthy):
    engine = Engine(MemStore(), agent=agent(verdict()))
    new = engine.process(healthy)
    assert [(a.rule_id, a.severity) for a in new] == [(RULE_ID, "warning")]
    assert STATUS.layer_agreement == "single" and STATUS.layers_alerting == ["llm"]
    assert engine.process(advance(healthy)) == []  # latched, no duplicate


def test_engine_three_layers_on_attack_replay():
    series = load_series("snapshots_attack.jsonl")
    ml_fired = []

    def ml_layer(window):
        s = window[-1]
        r = next((x for x in s.reserves if x.deployment_id == "lend-eth" and x.asset == "WETH"), None)
        if r and r.utilization_bps >= 9000:
            ml_fired.append(s.block_number)
            return [mk("R6_ML_ANOMALY", "high", "lend-eth", "WETH").model_copy(update={"block_number": s.block_number, "block_time": s.block_time, "detected_at": s.block_time, "network": s.network})], []
        return [], []

    def llm(system, user):
        payload = json.loads(user)
        last = payload["snapshots"][-1]
        t = next((x for x in last["tokens"] if x["symbol"] == "rsETH"), None)
        if t and t["bridge_destination_nonce"] is not None and t["bridge_source_nonce"] is not None and t["bridge_destination_nonce"] > t["bridge_source_nonce"]:
            return verdict(phases=(1, 2))
        return verdict(severity="none", phases=[], dep=None, asset=None)

    engine = Engine(MemStore(), agent=AgentMonitor(cfg(), call=llm, min_interval_s=0), extra_layers=[ml_layer])
    emitted = []
    for s in series:
        emitted.extend(engine.process(s))
    layers = {consensus.layer_of(a) for a in emitted}
    assert {"rules", "llm"} <= layers
    assert any(a.rule_id == "R1_BRIDGE_INVARIANT" and a.severity == "critical" for a in emitted)
    llm_alerts = [a for a in emitted if a.rule_id == RULE_ID]
    assert llm_alerts and all(a.severity in ("warning", "high") for a in llm_alerts)
    assert STATUS.layer_agreement in ("partial", "full")


def test_engine_normal_replay_agent_silent_no_false_alert():
    engine = Engine(MemStore(), agent=agent(verdict(severity="none", phases=[], dep=None, asset=None)))
    emitted = [a for s in load_series("snapshots_normal.jsonl") for a in engine.process(s)]
    assert [a for a in emitted if a.severity in ("high", "critical")] == []


@pytest.mark.asyncio
async def test_live_agent_is_non_blocking_and_late_verdict_is_persisted(healthy):
    def slow(system, user):
        time.sleep(0.15)
        return verdict()

    a = AgentMonitor(cfg(), call=slow, min_interval_s=0, timeout_s=1)
    engine = Engine(MemStore(), agent=a)
    started = time.monotonic()
    assert engine.ingest(healthy, include_agent=False) == []
    assert time.monotonic() - started < 0.05
    engine._schedule_agent(list(engine.window))
    assert engine._agent_task is not None and not engine._agent_task.done()
    await engine._agent_task
    new, snapshot = await engine._poll_agent()
    assert snapshot.block_number == healthy.block_number
    assert [(x.rule_id, x.severity) for x in new] == [(RULE_ID, "warning")]
    assert engine.store.saved_alerts[0].id == new[0].id
    a.close()


@pytest.mark.asyncio
async def test_live_agent_has_one_bounded_inflight_request(healthy):
    a = AgentMonitor(cfg(), call=lambda s, u: (time.sleep(0.1), verdict())[1], min_interval_s=0, timeout_s=1)
    engine = Engine(MemStore(), agent=a)
    engine.ingest(healthy, include_agent=False)
    engine._schedule_agent(list(engine.window))
    first = engine._agent_task
    engine._schedule_agent(list(engine.window))
    assert engine._agent_task is first
    first.cancel()
    a.close()
