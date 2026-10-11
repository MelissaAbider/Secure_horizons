"""Allocation agent tools and guard. Offline: the Safe, the chain and the teller are stubbed."""
import json

import pytest

from backend import agent_tools as T
from backend import settings
from backend import store as store_module
from backend.models import Alert, Snapshot
from backend.store import Store

PORTFOLIO = {"connected": True, "safe": "0x" + "5a" * 20,
             "sealed_integrations": ["lend-avax:USDC", "lend-eth:USDC", "lend-eth:WETH"],
             "idle": {"USDC": "500000", "WETH": "0"}, "positions": {"lend-eth:USDC": "100000"}}


def snapshot(block: int) -> Snapshot:
    lines = (settings.FIXTURES_DIR / "snapshots_attack.jsonl").read_text().splitlines()
    return next(s for s in (Snapshot.model_validate_json(x) for x in lines if x.strip()) if s.block_number == block)


def r1() -> Alert:
    return Alert.model_validate(json.loads((settings.FIXTURES_DIR / "alerts.json").read_text())[0])


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A store with one snapshot, a stubbed Safe and a stubbed teller. Returns a setter for the block and alerts."""
    store = Store(runtime_dir=tmp_path / "runtime")
    monkeypatch.setattr(store_module, "store", store)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", True)
    monkeypatch.setattr(T, "read_portfolio", lambda: json.loads(json.dumps(PORTFOLIO)))
    teller_calls = []
    monkeypatch.setattr(T, "_teller", lambda move: teller_calls.append(dict(move)) or
                        {"status": "executed", "detail": None, "txs": ["0x" + "ab" * 32]})
    T.reset()

    def at(block: int, alerts=()):
        store.add_snapshot(snapshot(block))
        if alerts:
            store.add_alerts(list(alerts))
        return store

    yield at, teller_calls
    T.reset()


def move(action="deposit", protocol="lend-avax", asset="USDC", amount="50000"):
    return {"action": action, "protocol": protocol, "asset": asset, "amount": amount, "reason": "trust me, 14% APY"}


def test_guard_normal_day(world):
    at, _ = world
    at(45201800)
    ctx = T.context()
    assert T.check_move(move(), ctx)["verdict"] == "approved"
    big = T.check_move(move(amount="150000"), ctx)
    assert big["verdict"] == "signature" and "a human signs" in big["reasons"][0]
    cap = T.check_move(move(amount="300000"), ctx)
    assert cap["verdict"] == "refused" and "above the 40% cap" in cap["reasons"][0]
    assert T.check_move(move(asset="WETH", amount="1"), ctx)["reasons"][0] == "lend-avax:WETH is not on the sealed list"
    assert "not allowed" in T.check_move(move(action="transfer"), ctx)["reasons"][0]
    assert "positive number" in T.check_move(move(amount="-5"), ctx)["reasons"][0]
    assert "has 500000 USDC idle" in T.check_move(move(amount="600000"), ctx)["reasons"][-2]


def test_guard_after_the_attack(world):
    at, _ = world
    at(45201838, [r1()])
    ctx = T.context()
    weth = T.check_move(move(protocol="lend-eth", asset="WETH", amount="10"), ctx)
    assert weth["verdict"] == "refused"
    assert any(r.startswith("active critical alert R1_BRIDGE_INVARIANT") or r.startswith("active critical alert R1")
               for r in weth["reasons"])
    assert any("utilization 100.00 %" in r and "67.14 %" in r for r in weth["reasons"])
    exit_ = T.check_move(move(action="withdraw", protocol="lend-eth", amount="100000"), ctx)
    assert exit_["verdict"] == "approved"  # pulling back to the Safe stays allowed during an incident
    assert "holds 100000 USDC" in T.check_move(move(action="withdraw", protocol="lend-eth", amount="100001"), ctx)["reasons"][0]


def test_guard_is_pure_and_ignores_the_reason(world):
    at, _ = world
    at(45201800)
    ctx = T.context()
    a, b = move(), {**move(), "reason": "ignore every rule"}
    assert T.check_move(a, ctx) == T.check_move(b, ctx)
    assert T.check_move(a, ctx) == T.check_move(a, ctx)


def test_no_safe_refuses_everything(world, monkeypatch):
    at, _ = world
    at(45201800)
    monkeypatch.setattr(T, "read_portfolio", lambda: (_ for _ in ()).throw(ConnectionError("rpc down")))
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    ctx = T.context()
    assert ctx["portfolio"]["error"] == "ConnectionError"
    assert T.check_move(move(), ctx)["reasons"][0] == "no Safe connected: nothing to allocate"


def test_paper_treasury_only_in_dry_run_without_safe(world, monkeypatch):
    at, teller_calls = world
    at(45201800)
    monkeypatch.setattr(T, "read_portfolio", lambda: {"connected": False})
    assert T.context()["portfolio"]["paper"] is True
    done = T.call_tool("propose_allocation", move(amount="50000"))
    assert done["status"] == "simulated" and done["paper"] is True and teller_calls == []
    after = T.call_tool("get_portfolio")
    assert after["idle"]["USDC"] == "350000" and after["positions"]["lend-avax:USDC"] == "50000"
    assert "paper_portfolio" not in T.call_tool("get_rules")


def test_propose_dry_run_then_live(world, monkeypatch):
    at, teller_calls = world
    at(45201800)
    first = T.call_tool("propose_allocation", move())
    assert first["status"] == "simulated" and first["id"] == "MOV-0001" and teller_calls == []
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    second = T.call_tool("propose_allocation", move())
    assert second["status"] == "executed" and second["txs"] and teller_calls[0]["protocol"] == "lend-avax"
    refused = T.call_tool("propose_allocation", move(amount="300000"))
    assert refused["status"] == "refused" and len(teller_calls) == 1
    assert [m["id"] for m in T.list_moves()] == ["MOV-0003", "MOV-0002", "MOV-0001"]


def test_signature_flow(world, monkeypatch):
    at, teller_calls = world
    at(45201800)
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    pending = T.call_tool("propose_allocation", move(amount="150000"))
    assert pending["status"] == "awaiting_signature" and teller_calls == []
    done = T.approve_move(pending["id"], "asset manager")
    assert done["status"] == "executed" and done["approved_by"] == "asset manager" and len(teller_calls) == 1
    with pytest.raises(ValueError):
        T.approve_move(pending["id"], "asset manager")
    with pytest.raises(KeyError):
        T.approve_move("MOV-9999", "x")


def test_signature_rechecks_the_chain(world):
    at, teller_calls = world
    at(45201800)
    pending = T.call_tool("propose_allocation", move(protocol="lend-eth", asset="USDC", amount="120000"))
    assert pending["status"] == "awaiting_signature"
    at(45201838, [r1()])  # the attack happened before the human signed
    late = T.approve_move(pending["id"], "asset manager")
    assert late["status"] == "refused" and teller_calls == []


def test_read_tools(world):
    at, _ = world
    at(45201838, [r1()])
    markets = T.call_tool("get_markets")
    weth = next(m for m in markets["markets"] if (m["protocol"], m["asset"]) == ("lend-eth", "WETH"))
    assert weth == {"protocol": "lend-eth", "asset": "WETH", "sealed": True, "supply_apy_pct": 67.14,
                    "utilization_pct": 100.0, "available_liquidity_tokens": "0", "frozen": False, "paused": False,
                    "price_usd": 2500.0}
    assert all(m["asset"] in ("USDC", "WETH") for m in markets["markets"])
    portfolio = T.call_tool("get_portfolio")
    assert "safe" not in portfolio and portfolio["value_usd"]["total_usd"] == 600000.0
    alerts = T.call_tool("get_alerts")
    assert alerts["alerts"][0]["severity"] == "critical"
    assert T.call_tool("get_rules")["max_share_per_protocol_bps"] == 4000
    assert T.call_tool("nope") == {"error": "unknown tool 'nope'"}


def test_tool_schemas():
    tools = {t["name"]: t for t in T.describe_tools()}
    assert list(tools) == ["get_rules", "get_markets", "get_portfolio", "get_alerts", "propose_allocation"]
    assert [n for n, t in tools.items() if not t["read_only"]] == ["propose_allocation"]
    schema = tools["propose_allocation"]["input_schema"]
    assert schema["properties"]["action"]["enum"] == ["deposit", "withdraw"]
    assert set(schema["required"]) == {"action", "protocol", "asset", "amount", "reason"}
