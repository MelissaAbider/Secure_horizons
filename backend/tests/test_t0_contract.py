"""T0-01..T0-03: fixtures follow the contract (TASKS.md 2.6, 2.7, 2.8, 2.13) and types.ts mirrors models.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

from eth_utils import keccak

from backend import fixtures, models

ROOT = Path(__file__).resolve().parents[2]
RULE_IDS = {"R1_BACKING_DROP", "R2_LIQUIDITY_DROP", "R3_UTILIZATION_HIGH", "R4_POSITION_STUCK", "R5_RESERVE_FROZEN"}


def test_fixtures_validate() -> None:
    models.Health.model_validate(fixtures.load("health.json"))
    models.StateResponse.model_validate(fixtures.load("state.json"))
    for points in fixtures.load("series.json").values():
        [models.SeriesPoint.model_validate(p) for p in points]
    [models.Alert.model_validate(a) for a in fixtures.load("alerts.json")]
    [models.Decision.model_validate(d) for d in fixtures.load("decisions.json")]
    models.VerifyResult.model_validate(fixtures.load("verify.json"))
    models.Incident.model_validate(fixtures.load("incident.json"))
    [models.Dependency.model_validate(d) for d in fixtures.load("dependencies.json")]
    models.EvalMetrics.model_validate(fixtures.load("metrics.json"))
    models.DemoRun.model_validate(fixtures.load("demo_run.json"))
    models.RunRecord.model_validate(fixtures.load("run_record.example.json"))
    for name in ("snapshots_attack.jsonl", "snapshots_normal.jsonl"):
        rows = fixtures.load_jsonl(name)
        assert len(rows) == 41
        [models.Snapshot.model_validate(r) for r in rows]


def test_fixture_story() -> None:
    alerts = [models.Alert.model_validate(a) for a in fixtures.load("alerts.json")]
    assert {a.rule_id for a in alerts} <= RULE_IDS
    decision = models.Decision.model_validate(fixtures.load("decisions.json")[0])
    assert decision.id == "DEC-fuji-45201812-1"
    assert [(a.type, a.mode) for a in decision.actions] == [
        ("NOTIFY", "auto"), ("PAUSE_DEPOSITS", "auto"),
        ("EMERGENCY_WITHDRAW", "auto"), ("EMERGENCY_WITHDRAW", "auto"), ("EMERGENCY_WITHDRAW", "auto"), ("EMERGENCY_WITHDRAW", "auto"),
        ("OPEN_INCIDENT", "auto"), ("UNPAUSE_DEPOSITS", "human"),
    ]
    withdrawals = [(a.params["deployment_id"], a.params["asset"]) for a in decision.actions if a.type == "EMERGENCY_WITHDRAW"]
    assert withdrawals == [("lend-eth", "USDC"), ("lend-eth", "WETH"), ("lend-avax", "USDC"), ("lend-avax", "WETH")]
    incident = models.Incident.model_validate(fixtures.load("incident.json"))
    assert incident.saved_usd == 1325000.0 and incident.at_risk_usd == 0.0
    assert incident.dora and incident.dora.is_major and incident.dora.thresholds_met == ["9(1)", "9(4)"]
    state = models.StateResponse.model_validate(fixtures.load("state.json"))
    assert state.positions == []
    assert state.totals == {"value_usd": 1325000.0, "withdrawable_usd": 0.0, "idle_usd": 1325000.0, "at_risk_usd": 0.0}
    verify = models.VerifyResult.model_validate(fixtures.load("verify.json"))
    assert verify.match and verify.stored_hash == decision.record_hash
    dep = fixtures.load("deployments.example.json")
    assert set(dep) >= {"network", "chain_id", "assets", "contracts", "lending", "roles"}
    assert set(dep["contracts"]) == {"MockBridge", "MockOracle", "TreasuryVault", "EvidenceRegistry"}
    assert [x["id"] for x in dep["lending"]] == ["lend-eth", "lend-avax"]
    record = models.RunRecord.model_validate(fixtures.load("run_record.example.json"))
    assert set(record.treasury_supplied_at_start) == {"lend-eth:USDC", "lend-eth:WETH", "lend-avax:USDC", "lend-avax:WETH"}


def test_record_hash_recomputes() -> None:
    decision = models.Decision.model_validate(fixtures.load("decisions.json")[0])
    body = decision.model_dump(mode="json", exclude={"record_hash", "anchor_tx", "anchor_block"})
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert "0x" + keccak(canonical).hex() == decision.record_hash


def test_types_ts_mirrors_models() -> None:
    """Every Pydantic model has a TypeScript interface with exactly the same field names."""
    ts = (ROOT / "frontend" / "src" / "types.ts").read_text(encoding="utf-8")
    interfaces = {m.group(1): set(re.findall(r"^\s+(\w+):", m.group(2), re.M))
                  for m in re.finditer(r"export interface (\w+) \{(.*?)\n\}", ts, re.S)}
    for name, model in vars(models).items():
        if isinstance(model, type) and issubclass(model, models.BaseModel) and model is not models.BaseModel:
            assert name in interfaces, f"{name} missing in types.ts"
            assert interfaces[name] == set(model.model_fields), f"{name}: types.ts and models.py differ"
