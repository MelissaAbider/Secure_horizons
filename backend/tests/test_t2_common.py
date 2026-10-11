"""T2 shared helpers and reset (TASKS.md T2, tests T2-06 to T2-09, T2-12, T2-13). Pure, no chain."""
import io
import json
from datetime import datetime, timezone

import pytest

from backend import settings
from backend.models import RunRecord
from scenario import common, reset
from scenario.common import Emitter, ScenarioError, maintenance, new_run_id, units, write_run_record


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    return tmp_path


def quiet() -> Emitter:
    return Emitter("RUN-test", json_mode=True, stream=io.StringIO())


def test_run_id_format():
    assert new_run_id("attack", 42, datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)) == "RUN-20261011080000-attack-42"


def test_write_run_record_roundtrip(data_dir):
    rec = RunRecord.model_validate_json((settings.FIXTURES_DIR / "run_record.example.json").read_text())
    path = write_run_record(rec)
    assert path == data_dir / "runs" / "RUN-20261011080000-attack-42.json"
    assert RunRecord.model_validate_json(path.read_text()) == rec


def test_emitter_json_line():
    stream = io.StringIO()
    Emitter("RUN-x", json_mode=True, stream=stream)("borrow", "borrow 1", block=12, tx_hash="0xab")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert set(json.loads(lines[0])) == {"run_id", "step", "status", "block", "tx_hash", "msg", "at"}


def test_units():
    assert units(150, "WETH") == 150 * 10**18
    assert units(400000, "USDC") == 400000 * 10**6


def test_maintenance_flag_lifecycle(data_dir):
    flag = data_dir / "runtime" / settings.NETWORK / "maintenance.flag"
    with pytest.raises(RuntimeError):
        with maintenance(quiet()):
            assert flag.exists()
            raise RuntimeError("boom")
    assert not flag.exists()


def test_reset_runs_under_maintenance(data_dir, tmp_path, monkeypatch):
    deployment = tmp_path / "local.json"
    deployment.write_text('{"deployed_at_block": 1}')
    monkeypatch.setattr(settings, "DEPLOYMENTS_FILE", deployment)
    seen = {}

    def fake_seed(emit, manage_maintenance=True):
        seen["flag"] = common.maintenance_flag_path().exists()
        seen["manage_maintenance"] = manage_maintenance

    monkeypatch.setattr(reset, "run_seed", fake_seed)
    reset.run_reset(quiet(), deploy_cmd=["sh", "-c", f"echo '{{\"deployed_at_block\": 2}}' > {deployment}"])
    assert seen == {"flag": True, "manage_maintenance": False}
    assert not common.maintenance_flag_path().exists()

    with pytest.raises(ScenarioError):
        reset.run_reset(quiet(), deploy_cmd=["false"])
    assert not common.maintenance_flag_path().exists()

    with pytest.raises(ScenarioError):  # deployment command succeeded but did not rewrite the file
        reset.run_reset(quiet(), deploy_cmd=["true"])
