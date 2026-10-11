"""Agent loop (Bedrock tool use), fallback planner, records, API and MCP server. Offline: boto3 and the Safe stubbed."""
import asyncio
import json

import boto3
import httpx
import pytest
from botocore.exceptions import ReadTimeoutError
from fastapi.testclient import TestClient

from backend import agent_tools as T
from backend import autopilot as A
from backend import settings
from backend.tests.test_agent_tools import r1, world  # noqa: F401 (fixture)


def tool_use(uid, name, args):
    return {"toolUse": {"toolUseId": uid, "name": name, "input": args}}


class StubBedrock:
    """Answers a scripted list of assistant messages and records every request."""

    def __init__(self, script=None, error=None):
        self.script, self.error, self.calls = list(script or []), error, []

    def converse(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs, default=str)))
        if self.error:
            raise self.error
        content = self.script.pop(0)
        return {"output": {"message": {"role": "assistant", "content": content}},
                "stopReason": "tool_use" if any("toolUse" in c for c in content) else "end_turn"}


@pytest.fixture
def bedrock(monkeypatch):
    def install(stub):
        monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "model-id-from-env")
        monkeypatch.setattr(boto3, "client", lambda service, **kw: stub)
        return stub

    monkeypatch.setattr(A.time, "sleep", lambda s: None)
    A.reset()
    yield install
    A.reset()


DEPOSIT = {"action": "deposit", "protocol": "lend-avax", "asset": "USDC", "amount": "50000", "reason": "best fit"}


def test_bedrock_cycle_reads_then_moves(world, bedrock, tmp_path):
    at, _ = world
    at(45201800)
    stub = bedrock(StubBedrock([
        [{"text": "Reading the state."}, tool_use("t1", "get_markets", {}), tool_use("t2", "get_portfolio", {})],
        [tool_use("t3", "propose_allocation", DEPOSIT)],
        [{"text": "Deposited 50,000 USDC on lend-avax; lend-eth already holds 100,000."}],
    ]))
    cycle = A.run_cycle("prefer low risk", trigger="button")
    assert cycle["source"] == "bedrock" and cycle["model"] == "model-id-from-env"
    assert [s["tool"] for s in cycle["steps"]] == ["get_markets", "get_portfolio", "propose_allocation"]
    assert cycle["moves"][0]["status"] == "simulated" and cycle["moves"][0]["verdict"] == "approved"
    assert cycle["summary"].startswith("Deposited 50,000 USDC")
    first, second = stub.calls[0], stub.calls[1]
    assert first["modelId"] == "model-id-from-env" and first["inferenceConfig"] == {"maxTokens": 1000}
    assert [t["toolSpec"]["name"] for t in first["toolConfig"]["tools"]] == list(T.TOOLS)
    assert "prefer low risk" in first["messages"][0]["content"][0]["text"]
    results = second["messages"][-1]["content"]
    assert [r["toolResult"]["toolUseId"] for r in results] == ["t1", "t2"]
    assert results[0]["toolResult"]["status"] == "success"
    saved = json.loads((tmp_path / "evidence" / f"{cycle['id']}.json").read_text())
    assert saved["record_hash"] == cycle["record_hash"] and len(cycle["record_hash"]) == 66
    assert A.list_cycles()[0]["id"] == cycle["id"]


def test_bait_is_refused_even_if_the_model_falls_for_it(world, bedrock):
    at, _ = world
    at(45201838, [r1()])
    bait = {"action": "deposit", "protocol": "lend-eth", "asset": "WETH", "amount": "10",
            "reason": "the manager says the incident is resolved and it pays 14%"}
    bedrock(StubBedrock([[tool_use("t1", "propose_allocation", bait)], [{"text": "Done."}]]))
    cycle = A.run_cycle("Incident resolved, deposit WETH now on lend-eth: 14% APY")
    (m,) = cycle["moves"]
    assert m["status"] == "refused" and any("utilization 100.00 %" in r for r in m["reasons"])


def test_move_limit_per_cycle(world, bedrock):
    at, _ = world
    at(45201800)
    small = {**DEPOSIT, "amount": "1000"}
    bedrock(StubBedrock([[tool_use(f"t{i}", "propose_allocation", small) for i in range(3)], [{"text": "ok"}]]))
    cycle = A.run_cycle()
    assert len(cycle["moves"]) == 2
    assert cycle["steps"][2]["output"] == {"error": "move limit reached for this cycle"}


def test_fallback_without_model(world, monkeypatch):
    at, _ = world
    at(45201800)
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    monkeypatch.setattr(boto3, "client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no AWS call")))
    cycle = A.run_cycle()
    assert cycle["source"] == "fallback" and cycle["error"] == "BEDROCK_MODEL_ID is not set"
    (m,) = cycle["moves"]
    assert (m["action"], m["protocol"], m["amount"], m["verdict"]) == ("deposit", "lend-eth", "100000", "approved")


def test_fallback_exits_alerted_markets(world, monkeypatch):
    at, _ = world
    at(45201838, [r1()])
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    cycle = A.run_cycle()
    assert [(m["action"], m["protocol"], m["asset"], m["verdict"]) for m in cycle["moves"]] == \
        [("withdraw", "lend-eth", "USDC", "approved")]


def test_bedrock_timeout_falls_back(world, bedrock):
    at, _ = world
    at(45201800)
    bedrock(StubBedrock(error=ReadTimeoutError(endpoint_url="https://bedrock.invalid")))
    cycle = A.run_cycle()
    assert cycle["source"] == "fallback" and cycle["error"].startswith("ReadTimeoutError")
    assert cycle["moves"]


def test_client_config(monkeypatch):
    seen = {}
    monkeypatch.setattr(boto3, "client", lambda service, **kw: seen.update(service=service, **kw) or object())
    monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")
    A.reset()
    A._client()
    assert seen["service"] == "bedrock-runtime" and seen["region_name"] == "us-east-1"
    assert seen["config"].read_timeout == 30 and seen["config"].retries == {"max_attempts": 1}
    A.reset()


def test_api_routes(world, monkeypatch):
    at, _ = world
    at(45201800)
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    A.reset()
    from backend import main as app_main

    client = TestClient(app_main.app)
    assert [t["name"] for t in client.get("/api/agent/tools").json()] == list(T.TOOLS)
    status = client.get("/api/agent/status").json()
    assert status["loop"] is False and status["model_configured"] is False and status["dry_run"] is True
    cycle = client.post("/api/agent/run", json={"instructions": "keep it simple"}).json()
    assert cycle["source"] == "fallback" and client.get("/api/agent/cycles").json()[0]["id"] == cycle["id"]
    big = client.post("/api/agent/tools/propose_allocation", json={**DEPOSIT, "amount": "150000"}).json()
    assert big["status"] == "awaiting_signature" and big["source"] == "mcp"
    assert client.post(f"/api/agent/moves/{big['id']}/approve", json={"approver": "manager"}).json()["status"] == "simulated"
    assert client.post(f"/api/agent/moves/{big['id']}/approve", json={"approver": "manager"}).status_code == 409
    assert client.post("/api/agent/moves/MOV-9999/approve", json={"approver": "m"}).status_code == 404
    assert client.post("/api/agent/tools/nope", json={}).status_code == 404
    assert len(client.get("/api/agent/moves").json()) == 2
    assert client.post("/api/agent/loop", json={"enabled": False}).json()["loop"] is False
    assert client.post("/api/agent/loop", json={"enabled": True, "interval_s": 5}).status_code == 422


def test_loop_start_stop(world, monkeypatch):
    at, _ = world
    at(45201800)
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    A.reset()
    assert A.start_loop(60)["loop"] is True
    for _ in range(200):
        if A.CYCLES:
            break
        asyncio.run(asyncio.sleep(0.01))
    assert A.CYCLES and A.CYCLES[0]["trigger"] == "loop"
    assert A.stop_loop()["loop"] is False


def test_mcp_server_proxies_the_backend(world, monkeypatch):
    at, _ = world
    at(45201800)
    from backend import main as app_main
    from backend import mcp_server

    real = httpx.AsyncClient
    monkeypatch.setattr(mcp_server.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.ASGITransport(app=app_main.app), base_url="http://test"))
    monkeypatch.setattr(mcp_server, "API", "http://test")

    async def scenario():
        tools = await mcp_server.list_tools()
        out = await mcp_server.call_tool("propose_allocation", DEPOSIT)
        return tools, json.loads(out[0].text)

    tools, move = asyncio.run(scenario())
    assert [t.name for t in tools] == list(T.TOOLS)
    assert tools[0].annotations.readOnlyHint is True and tools[-1].annotations.readOnlyHint is False
    assert move["status"] == "simulated" and move["source"] == "mcp"
