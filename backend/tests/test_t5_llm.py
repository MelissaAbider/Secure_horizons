"""T5-13 to T5-16: optional Bedrock drafting, never blocking (TASKS.md T5 6). No network: boto3 is stubbed."""
import boto3
import pytest
from botocore.exceptions import ReadTimeoutError

from backend import llm, settings
from backend.tests.test_t5_factories import run_reacted_incident

FACTS = {"id": "INC-20261011-001", "severity": "critical", "saved_usd": 1325000.0}


class StubClient:
    def __init__(self, text="The platform paused deposits and withdrew 1,325,000 USD to the vault.", error=None):
        self.text, self.error, self.calls = text, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": f"  {self.text}  "}]}}}


@pytest.fixture(autouse=True)
def fresh_llm(monkeypatch):
    llm.reset()
    yield
    llm.reset()


def _stub(monkeypatch, stub):
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: stub)


def test_disabled_uses_template(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")

    def broken(*args, **kwargs):
        raise RuntimeError("boto3 must not be called")

    monkeypatch.setattr(boto3, "client", broken)
    assert llm.enabled() is False
    assert llm.draft_description(FACTS, fallback="TEMPLATE") == ("TEMPLATE", False)
    incident, _ = run_reacted_incident(monkeypatch)
    assert incident.dora.ai_drafted_sections == []


def test_bedrock_error_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "anthropic.claude-test")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    _stub(monkeypatch, StubClient(error=ReadTimeoutError(endpoint_url="https://bedrock.invalid")))
    assert llm.draft_description(FACTS, fallback="TEMPLATE") == ("TEMPLATE", False)
    assert llm.last_status() == "degraded"


def test_bedrock_success(monkeypatch):
    stub = StubClient()
    _stub(monkeypatch, stub)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    incident, _ = run_reacted_incident(monkeypatch, bedrock_model_id="anthropic.claude-test")
    assert stub.calls, "converse was not called"
    call = stub.calls[-1]
    assert call["modelId"] == "anthropic.claude-test"
    assert call["inferenceConfig"] == {"maxTokens": 400, "temperature": 0}
    assert llm.last_status() == "ok"
    assert incident.dora.ai_drafted_sections == ["Description"]
    md = incident.dora.report_markdown
    section = md[md.index("## 3. Description"):md.index("## 4.")]
    assert stub.text in section
    assert "_(AI-drafted, review required)_" in section


def test_rate_limit_and_cache(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "anthropic.claude-test")
    stub = StubClient()
    _stub(monkeypatch, stub)
    sleeps = []
    monkeypatch.setattr(llm.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.draft_description(FACTS, fallback="T")[1] is True
    assert llm.draft_description({**FACTS, "saved_usd": 0.0}, fallback="T")[1] is True
    assert len(sleeps) == 1 and sleeps[0] == pytest.approx(1.0)
    assert len(stub.calls) == 2
    assert llm.draft_description(FACTS, fallback="T")[1] is True
    assert len(stub.calls) == 2
