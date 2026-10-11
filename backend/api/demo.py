"""Demo routes: the dashboard's "Run attack" and "Reset" buttons (TASKS.md 2.9, T2 step 7). Owner: T2.

Each run is a `python -m scenario.attack|reset --json` subprocess; its JSON lines become the DemoRun log.
One attack or reset at a time (409 otherwise).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
from datetime import datetime, timezone
from typing import Callable, Literal, Optional, Protocol

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import fixtures, settings
from backend.models import DemoRun, DemoStep
from scenario.common import new_run_id
from scenario.params import attack_params

router = APIRouter()
MAX_LOG_LINES = 500
_RUNS: dict[str, DemoRun] = {}
_LOCK = threading.Lock()


class AttackBody(BaseModel):
    seed: Optional[int] = Field(default=None, ge=0)  # null: drawn here; 0: default parameters
    variant: Literal["default", "slow", "usdc"] = "default"


class Runner(Protocol):
    def start(self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]) -> None: ...


class SubprocessRunner:
    def start(self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]) -> None:
        proc = subprocess.Popen(argv, cwd=settings.ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env={**os.environ, "PYTHONUNBUFFERED": "1"})

        def pump() -> None:
            for line in proc.stdout:
                on_line(line.rstrip("\n"))
            on_exit(proc.wait())

        threading.Thread(target=pump, daemon=True).start()


_runner = SubprocessRunner()


def get_runner() -> Runner:
    return _runner


def _reset_store() -> None:
    from backend.store import store

    store.reset()


def _parse(line: str) -> tuple[str, Optional[DemoStep]]:
    """A scenario JSON line -> (log text, structured step); any other line is kept as is."""
    try:
        d = json.loads(line)
        text = f"[{d['block']}] {d['step']}: {d['msg']}" if d.get("block") is not None else f"{d['step']}: {d['msg']}"
        return text, DemoStep.model_validate(d)
    except (ValueError, KeyError, TypeError):
        return line, None


def _start(run: DemoRun, argv: list[str], runner: Runner) -> DemoRun:
    with _LOCK:
        busy = next((r.run_id for r in _RUNS.values() if r.status == "running"), None)
        if busy:
            raise HTTPException(409, f"demo run already running: {busy}")
        _RUNS[run.run_id] = run

    def on_line(line: str) -> None:
        text, step = _parse(line)
        with _LOCK:
            run.log = (run.log + [text])[-MAX_LOG_LINES:]
            if step is not None:
                run.steps = (run.steps + [step])[-MAX_LOG_LINES:]

    def on_exit(code: int) -> None:
        if code == 0 and run.kind == "reset":
            _reset_store()
        with _LOCK:
            run.finished_at = datetime.now(timezone.utc)
            run.status = "done" if code == 0 else "failed"
            if code != 0:
                run.log = (run.log + [f"exit code {code}"])[-MAX_LOG_LINES:]

    try:
        runner.start(argv, on_line, on_exit)
    except Exception:
        with _LOCK:
            _RUNS.pop(run.run_id, None)
        raise
    return run


@router.post("/demo/attack", response_model=DemoRun)
def start_attack(body: Optional[AttackBody] = None, runner: Runner = Depends(get_runner)):
    if settings.USE_FIXTURES:
        return fixtures.load("demo_run.json")
    body = body or AttackBody()
    seed = random.SystemRandom().randint(1, 999_999) if body.seed is None else body.seed
    run_id = new_run_id("attack", seed)
    run = DemoRun(run_id=run_id, kind="attack", variant=body.variant, seed=seed, status="running",
                  started_at=datetime.now(timezone.utc), params=attack_params(body.variant, seed).as_params())
    argv = [sys.executable, "-m", "scenario.attack", "--json", "--run-id", run_id, "--variant", body.variant,
            "--seed", str(seed)]
    return _start(run, argv, runner)


@router.post("/demo/reset", response_model=DemoRun)
def start_reset(runner: Runner = Depends(get_runner)):
    if settings.USE_FIXTURES:
        return fixtures.load("demo_run.json")
    run_id = new_run_id("reset", 0)
    run = DemoRun(run_id=run_id, kind="reset", status="running", started_at=datetime.now(timezone.utc))
    return _start(run, [sys.executable, "-m", "scenario.reset", "--json", "--run-id", run_id], runner)


@router.get("/demo/runs/{run_id}", response_model=DemoRun)
def get_run(run_id: str):
    if settings.USE_FIXTURES:
        return fixtures.load("demo_run.json")
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        return run.model_copy(deep=True)
