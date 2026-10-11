"""Agent: Bedrock proposal with fallback, pure guard, evidence record. No network: boto3 is stubbed."""
import json

import boto3
import pytest
from botocore.exceptions import ReadTimeoutError

from backend import agent, evidence, settings
from backend.tests.test_t5_factories import load_attack, make_alert_r1, make_reacted_series

SUPPLY_WETH = {"action": "supply", "deployment_id": "lend-eth", "asset": "WETH", "amount": "100", "reason": "x"}


class StubClient:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.text}]}}}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    agent.reset()
    monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    yield tmp_path
    agent.reset()


def _bedrock(monkeypatch, stub):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "anthropic.claude-test")
    monkeypatch.setattr(boto3, "client", lambda *a, **k: stub)


def _snap(block, reacted=True):
    return next(s for s in (make_reacted_series() if reacted else load_attack()) if s.block_number == block)


def test_refused_after_incident_with_three_reasons():
    result = agent.check_proposal(SUPPLY_WETH, _snap(45201838), [make_alert_r1()])
    assert result["allowed"] is False
    assert len(result["reasons"]) == 3
    alert, paused, liquidity = result["reasons"]
    assert alert.startswith("active critical alert R1_BACKING_DROP on global/rsETH since block 45201812")
    assert "1,325,000 USD" in alert
    assert paused.startswith("vault deposits are paused at block 45201838")
    assert liquidity.startswith("WETH liquidity on lend-eth is 0 at block 45201838 (utilization 100.00 %")


def test_allowed_on_normal_snapshot():
    assert agent.check_proposal(SUPPLY_WETH, _snap(45201800, reacted=False), []) == {"allowed": True, "reasons": []}
    withdraw = {**SUPPLY_WETH, "action": "withdraw", "deployment_id": "lend-avax", "asset": "USDC", "amount": "5000"}
    assert agent.check_proposal(withdraw, _snap(45201800, reacted=False), [])["allowed"] is True


def test_refuses_other_actions_and_bad_targets():
    snap = _snap(45201800, reacted=False)
    borrow = agent.check_proposal({**SUPPLY_WETH, "action": "borrow"}, snap, [])
    assert borrow["reasons"] == ["action 'borrow' is not allowed (only supply or withdraw)"]
    unknown = agent.check_proposal({**SUPPLY_WETH, "deployment_id": "lend-sol"}, snap, [])
    assert unknown["reasons"] == ["no reserve WETH on lend-sol at block 45201800"]
    zero = agent.check_proposal({**SUPPLY_WETH, "amount": "0"}, snap, [])
    assert zero["allowed"] is False
    warning_only = make_alert_r1().model_copy(update={"severity": "warning"})
    assert agent.check_proposal(SUPPLY_WETH, snap, [warning_only])["allowed"] is True


def test_check_is_pure():
    snap, alerts = _snap(45201838), [make_alert_r1()]
    before = (snap.model_dump(), [a.model_dump() for a in alerts], dict(SUPPLY_WETH))
    assert agent.check_proposal(SUPPLY_WETH, snap, alerts) == agent.check_proposal(SUPPLY_WETH, snap, alerts)
    assert (snap.model_dump(), [a.model_dump() for a in alerts], dict(SUPPLY_WETH)) == before


def test_bedrock_proposal(monkeypatch):
    answer = 'Here you go: {"action": "Supply", "deployment_id": "lend-avax", "asset": "USDC", "amount": 5000, ' \
             '"reason": "Utilization is moderate."}'
    stub = StubClient(text=answer)
    _bedrock(monkeypatch, stub)
    p = agent.propose("Put idle USDC to work", _snap(45201800, reacted=False))
    assert (p["action"], p["deployment_id"], p["asset"], p["amount"]) == ("supply", "lend-avax", "USDC", "5000")
    assert p["source"] == "bedrock" and p["model"] == "anthropic.claude-test"
    (call,) = stub.calls
    assert call["modelId"] == "anthropic.claude-test"
    assert call["inferenceConfig"] == {"maxTokens": 300}
    state = json.loads(call["messages"][0]["content"][0]["text"])["state"]
    assert state["block_number"] == 45201800 and "address" not in json.dumps(state)


@pytest.mark.parametrize("stub", [
    StubClient(error=ReadTimeoutError(endpoint_url="https://bedrock.invalid")),
    StubClient(text="I would supply WETH, it pays 14%."),
    StubClient(text='{"action": "supply", "asset": "WETH"}'),
], ids=["timeout", "no-json", "missing-keys"])
def test_fallback_when_bedrock_fails(monkeypatch, stub):
    _bedrock(monkeypatch, stub)
    p = agent.propose("deposit WETH", _snap(45201838))
    assert p["source"] == "fallback"
    assert {k: p[k] for k in ("action", "deployment_id", "asset", "amount")} == \
        {"action": "supply", "deployment_id": "lend-eth", "asset": "WETH", "amount": "100"}
    assert p["error"]


def test_fallback_without_model_id(monkeypatch):
    def broken(*a, **k):
        raise AssertionError("boto3 must not be called")

    monkeypatch.setattr(boto3, "client", broken)
    assert agent.propose("anything", _snap(45201838))["source"] == "fallback"


def test_record_written_with_hash(isolated):
    result = agent.run(agent.DEMO_MESSAGE, _snap(45201838), [make_alert_r1()])
    assert result["id"] == "AGT-45201838-1"
    assert result["check"]["allowed"] is False
    path = isolated / "AGT-45201838-1.json"
    stored = json.loads(path.read_text())
    assert stored == result
    body = {k: v for k, v in stored.items() if k != "record_hash"}
    assert stored["record_hash"] == evidence.keccak_hex(evidence.canonical_json(body))
    assert len(stored["record_hash"]) == 66
    assert agent.run("again", _snap(45201838), [])["id"] == "AGT-45201838-2"
    assert [r["id"] for r in agent.list_records()][0] in {"AGT-45201838-1", "AGT-45201838-2"}
    assert len(agent.list_records()) == 2


def test_demo_cli(capsys, isolated):
    assert agent.main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert out.count("\n- ") == 3
    assert (isolated / "AGT-45201838-1.json").exists()
