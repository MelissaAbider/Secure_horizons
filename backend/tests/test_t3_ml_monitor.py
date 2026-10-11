from pathlib import Path

from backend.ml_monitor import MLMonitor, RULE_ID, snapshot_features
from backend.tests.test_t3_rules import load_series


def test_ml_baseline_fits_and_is_hashed():
    model = MLMonitor(allow_non_live=True)
    model.evaluate(load_series("snapshots_normal.jsonl")[:1])
    assert model.status.available
    assert model.status.baseline_samples == 41
    assert model.status.threshold is not None
    assert model.status.model_hash.startswith("sha256:")


def test_normal_fixture_produces_no_ml_alert():
    model = MLMonitor(allow_non_live=True)
    series = load_series("snapshots_normal.jsonl")
    alerts = [a for i in range(len(series)) for a in model.evaluate(series[max(0, i - 19):i + 1])[0]]
    assert alerts == []


def test_attack_fixture_produces_capped_explainable_ml_alert():
    model = MLMonitor(allow_non_live=True)
    series = load_series("snapshots_attack.jsonl")
    alerts = [a for i in range(len(series)) for a in model.evaluate(series[max(0, i - 19):i + 1])[0]]
    assert alerts
    assert all(a.rule_id == RULE_ID and a.severity == "high" for a in alerts)
    assert all(a.metrics["layer"] == "ml" and a.metrics["score"] > a.metrics["threshold"] for a in alerts)
    assert any("bridge" in a.metrics["phases"] for a in alerts)


def test_missing_or_short_baseline_disables_ml_without_claiming_safe(tmp_path):
    missing = MLMonitor(baseline_path=tmp_path / "missing.jsonl", allow_non_live=True)
    assert not missing.status.available
    assert missing.evaluate(load_series("snapshots_normal.jsonl")[:1])[0] == []
    assert "unavailable" in missing.evaluate(load_series("snapshots_normal.jsonl")[:1])[1][0]

    short = tmp_path / "short.jsonl"
    short.write_text(load_series("snapshots_normal.jsonl")[0].model_dump_json() + "\n", encoding="utf-8")
    model = MLMonitor(baseline_path=short, allow_non_live=True)
    model.evaluate(load_series("snapshots_normal.jsonl")[:1])
    assert not model.status.available and model.status.last_error == "ValueError"


def test_features_have_no_addresses_or_prices():
    vector, named = snapshot_features(load_series("snapshots_attack.jsonl")[:3])
    assert len(vector) == len(named) == 13
    assert not any("address" in name or "price" in name for name in named)
