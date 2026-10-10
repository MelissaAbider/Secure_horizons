"""T4-21 to T4-23: verify, tamper, restore (TASKS.md T4 3.5, 3.8)."""
import json

from backend import cli
from backend.evidence import verify
from backend.tests.test_t4_fixtures import evidence_tmp, handle_r1_critical  # noqa: F401


def test_verify_match(evidence_tmp):
    (d,), _, _, _ = handle_r1_critical()
    result = verify(d.id)
    assert result.match is True
    assert result.diffs == []
    assert result.anchored is True
    assert result.stored_hash == result.recomputed_hash == d.record_hash
    assert result.anchor_tx == d.anchor_tx


def test_verify_tamper(evidence_tmp, capsys):
    (d,), _, _, _ = handle_r1_critical()

    assert cli.main(["tamper", d.id, "--field", "decision.actions.2.params.asset", "--value", "DAI"]) == 0
    assert "TAMPERED decision.actions.2.params.asset: USDC -> DAI" in capsys.readouterr().out
    assert cli.main(["verify", d.id]) == 1
    out = capsys.readouterr().out
    assert out.startswith("MISMATCH")
    assert "- record_hash:" in out
    assert "- action[2]: stored EMERGENCY_WITHDRAW/auto" in out
    assert "'asset': 'DAI'" in out

    assert cli.main(["restore", d.id]) == 0
    capsys.readouterr()
    assert cli.main(["verify", d.id]) == 0
    assert capsys.readouterr().out.startswith("MATCH")

    assert cli.main(["tamper", d.id, "--field", "inputs.snapshot.positions.1.withdrawable_now",
                     "--value", '"0"']) == 0
    capsys.readouterr()
    assert cli.main(["verify", d.id]) == 1
    out = capsys.readouterr().out
    assert out.startswith("MISMATCH")
    assert "- inputs_hash:" in out
    assert "action count: stored 8 != replanned 7" in out
    assert cli.main(["restore", d.id]) == 0


def test_verify_not_anchored(evidence_tmp):
    (d,), _, _, _ = handle_r1_critical()
    anchors_file = evidence_tmp / "anchors.json"
    anchors = json.loads(anchors_file.read_text())
    del anchors[d.record_hash]
    anchors_file.write_text(json.dumps(anchors))
    result = verify(d.id)
    assert result.anchored is False
    assert result.match is False
    assert any("not anchored" in diff for diff in result.diffs)
    assert cli.main(["verify", "DEC-x"]) == 2
