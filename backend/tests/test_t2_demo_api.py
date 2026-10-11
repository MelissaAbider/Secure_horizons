"""T2 demo API (TASKS.md T2, tests T2-50 to T2-55). A fake runner stands in for the subprocess."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import fixtures, settings
from backend.api import demo
from backend.main import app


class FakeRunner:
    def __init__(self):
        self.calls = []

    def start(self, argv, on_line, on_exit):
        self.calls.append({"argv": argv, "on_line": on_line, "on_exit": on_exit})


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(settings, "USE_FIXTURES", False)
    demo._RUNS.clear()
    fake = FakeRunner()
    app.dependency_overrides[demo.get_runner] = lambda: fake
    yield fake
    app.dependency_overrides.clear()
    demo._RUNS.clear()


client = TestClient(app)


def finish(runner, code=0):
    runner.calls[-1]["on_exit"](code)


def test_attack_starts_run(runner):
    r = client.post("/api/demo/attack", json={})
    assert r.status_code == 200
    run = r.json()
    assert run["kind"] == "attack" and run["status"] == "running" and 1 <= run["seed"] <= 999_999
    argv = runner.calls[0]["argv"]
    i = argv.index("-m")
    assert argv[i:] == ["-m", "scenario.attack", "--json", "--run-id", run["run_id"], "--variant", "default",
                        "--seed", str(run["seed"])]
    assert run["run_id"].endswith(f"-attack-{run['seed']}")
    finish(runner)

    run = client.post("/api/demo/attack", json={"seed": 0}).json()
    assert run["seed"] == 0 and run["params"]["chunk_weth"] == 100
    finish(runner)
    assert client.post("/api/demo/attack", json={"seed": 42}).json()["seed"] == 42


def test_log_and_exit_done(runner):
    run_id = client.post("/api/demo/attack", json={"seed": 0}).json()["run_id"]
    line = {"run_id": run_id, "step": "forged_mint", "status": "ok", "block": 12, "tx_hash": None, "msg": "x", "at": "2026-10-11T08:00:00Z"}
    runner.calls[0]["on_line"](json.dumps(line))
    finish(runner)
    run = client.get(f"/api/demo/runs/{run_id}").json()
    assert run["log"] == ["[12] forged_mint: x"] and run["status"] == "done" and run["finished_at"]
    assert [(s["step"], s["block"], s["status"]) for s in run["steps"]] == [("forged_mint", 12, "ok")]


def test_exit_nonzero_failed(runner):
    run_id = client.post("/api/demo/attack", json={"seed": 0}).json()["run_id"]
    finish(runner, 3)
    run = client.get(f"/api/demo/runs/{run_id}").json()
    assert run["status"] == "failed" and run["log"][-1] == "exit code 3"


def test_reset_calls_store_reset_only_on_success(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(demo, "_reset_store", lambda: calls.append(1))
    run = client.post("/api/demo/reset").json()
    assert run["kind"] == "reset" and runner.calls[0]["argv"][-4:] == ["scenario.reset", "--json", "--run-id", run["run_id"]]
    finish(runner, 0)
    assert calls == [1]
    client.post("/api/demo/reset")
    finish(runner, 1)
    assert calls == [1]


def test_404_and_409_and_422(runner):
    r = client.get("/api/demo/runs/RUN-nope")
    assert r.status_code == 404 and r.json() == {"detail": "run not found"}
    run_id = client.post("/api/demo/attack", json={"seed": 0}).json()["run_id"]
    for path in ("/api/demo/attack", "/api/demo/reset"):
        r = client.post(path, json={})
        assert r.status_code == 409 and run_id in r.json()["detail"]
    assert client.post("/api/demo/attack", json={"variant": "foo"}).status_code == 422
    assert client.post("/api/demo/attack", json={"seed": -1}).status_code == 422


def test_fixture_mode(runner, monkeypatch):
    monkeypatch.setattr(settings, "USE_FIXTURES", True)
    expected = fixtures.load("demo_run.json")
    assert client.post("/api/demo/attack", json={}).json() == expected
    assert client.post("/api/demo/reset").json() == expected
    assert client.get("/api/demo/runs/anything").json() == expected
    assert runner.calls == []
