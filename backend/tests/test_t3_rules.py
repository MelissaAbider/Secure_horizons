from pathlib import Path

from backend.engine import Engine
from backend.models import Snapshot
from backend.rules import evaluate_all, load_rules, rules_version


class MemStore:
    def __init__(self):
        self.generation = 0
        self.saved_snapshots = []
        self.saved_alerts = []

    def add_snapshot(self, snapshot):
        self.saved_snapshots.append(snapshot)

    def add_alerts(self, alerts):
        self.saved_alerts.extend(alerts)


def load_series(name: str) -> list[Snapshot]:
    path = Path(__file__).resolve().parents[2] / "fixtures" / name
    return [Snapshot.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


def replay(name: str):
    store = MemStore()
    engine = Engine(store)
    alerts = []
    for snapshot in load_series(name):
        alerts.extend(engine.process(snapshot))
    return alerts


def test_rules_file_is_versioned():
    cfg = load_rules()
    assert cfg["version"] == 3
    assert cfg["window_snapshots"] == 20
    assert cfg["_version"] == rules_version()
    assert len(cfg["_version"]) == 71


def test_attack_replay_matches_kelpdao_causal_chain():
    alerts = replay("snapshots_attack.jsonl")
    assert [(a.block_number, a.rule_id, a.severity, a.deployment_id, a.asset) for a in alerts] == [
        (45201812, "R1_BRIDGE_INVARIANT", "critical", None, "rsETH"),
        (45201814, "R2_COLLATERAL_SURGE", "critical", "lend-eth", "rsETH"),
        (45201826, "R3_LIQUIDITY_DRAIN", "high", "lend-eth", "WETH"),
        (45201832, "R3_LIQUIDITY_DRAIN", "critical", "lend-eth", "WETH"),
        (45201836, "R4_EXITABILITY_DROP", "high", "lend-eth", "WETH"),
        (45201838, "R4_EXITABILITY_DROP", "critical", "lend-eth", "WETH"),
        (45201878, "R5_CONTAINMENT", "critical", None, "rsETH"),
        (45201878, "R5_CONTAINMENT", "critical", "lend-eth", "rsETH"),
    ]
    r1 = alerts[0]
    assert r1.metrics["conservation_gap"] == 5000.0
    assert r1.metrics["source_nonce"] == 307
    assert r1.metrics["destination_nonce"] == 308
    assert r1.exposure_usd == 1_325_000.0


def test_normal_replay_has_no_alerts():
    assert replay("snapshots_normal.jsonl") == []


def test_r1_does_not_depend_on_display_backing_ratio():
    snapshot = load_series("snapshots_attack.jsonl")[6]
    token = next(token for token in snapshot.tokens if token.symbol == "rsETH")
    altered = token.model_copy(update={"backing_ratio_bps": 10_000})
    snapshot = snapshot.model_copy(update={"tokens": [altered if t.symbol == "rsETH" else t for t in snapshot.tokens]})
    alerts = evaluate_all([snapshot], load_rules())
    assert [alert.rule_id for alert in alerts] == ["R1_BRIDGE_INVARIANT"]


def test_bridge_nonce_mismatch_is_critical_even_without_value_gap():
    snapshot = load_series("snapshots_normal.jsonl")[6]
    token = next(token for token in snapshot.tokens if token.symbol == "rsETH")
    altered = token.model_copy(update={"bridge_destination_nonce": token.bridge_source_nonce + 1})
    snapshot = snapshot.model_copy(update={"tokens": [altered if t.symbol == "rsETH" else t for t in snapshot.tokens]})
    alerts = evaluate_all([snapshot], load_rules())
    assert len(alerts) == 1
    assert alerts[0].rule_id == "R1_BRIDGE_INVARIANT"
    assert alerts[0].severity == "critical"
