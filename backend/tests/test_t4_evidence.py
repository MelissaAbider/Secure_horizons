"""T4-11 to T4-13: canonical JSON and hashes (TASKS.md T4 3.5)."""
from backend.evidence import canonical_json, inputs_hash, keccak_hex, record_hash
from backend.models import Decision
from backend.tests.test_t4_fixtures import evidence_tmp, handle_r1_critical, make_alert  # noqa: F401


def test_canonical_json():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonical_json({"x": "é"}) == '{"x":"é"}'
    assert keccak_hex("") == "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"


def test_hash_roundtrip(evidence_tmp):
    (decision,), alerts, snap, _ = handle_r1_critical()
    assert record_hash(Decision.model_validate_json(decision.model_dump_json())) == decision.record_hash
    other = make_alert("R2_LIQUIDITY_DROP", "high", snap, "lend-eth", "WETH", 375000.0)
    pair = [alerts[0], other]
    assert inputs_hash(pair, snap) == inputs_hash(pair, snap)
    assert inputs_hash(pair, snap) == inputs_hash(list(reversed(pair)), snap)
    assert inputs_hash(alerts, snap) == decision.inputs_hash


def test_record_hash_scope(evidence_tmp):
    (decision,), _, _, _ = handle_r1_critical()
    assert record_hash(decision.model_copy(update={"anchor_tx": "0x" + "ab" * 32})) == decision.record_hash
    changed = decision.model_copy(deep=True)
    changed.actions[0].note = "channels: log,sms"
    assert record_hash(changed) != decision.record_hash
