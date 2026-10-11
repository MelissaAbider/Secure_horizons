"""Reset: redeploy every contract then seed again, under the maintenance flag (TASKS.md T2 step 6). Owner: T2.

python -m scenario.reset [--json] [--run-id RUN-...]
On fuji this costs gas, takes about 2 minutes and changes every address (deployments/fuji.json is rewritten).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Optional, Sequence

from backend import chain, settings
from scenario.common import Emitter, ScenarioError, maintenance, new_run_id, run_main
from scenario.seed import run_seed


def _fingerprint() -> Optional[tuple]:
    f = settings.DEPLOYMENTS_FILE
    if not f.exists():
        return None
    try:
        block = json.loads(f.read_text(encoding="utf-8")).get("deployed_at_block")
    except ValueError:
        block = None
    return f.stat().st_mtime_ns, block


def refund_safe(emit: Emitter) -> None:
    """T10: the connected Safe gets its test tokens again on the new token contracts. Its list points to the old
    markets, so the dashboard asks the owner to seal it again (a new signature)."""
    try:
        from sealed import live
        from sealed import safe as S

        state = S.load_state()
        if not len(chain.w3().eth.get_code(state["safe"])):
            return
        live.fund(state)
    except Exception as exc:  # no connected Safe on this network: nothing to do
        emit("safe", f"no Safe to credit ({type(exc).__name__})", status="info")
        return
    emit("safe", f"Safe {state['safe']} credited with test tokens; its list must be sealed again", status="info")


def run_reset(emit: Emitter, deploy_cmd: Optional[Sequence[str]] = None) -> None:
    command = list(deploy_cmd) if deploy_cmd is not None else [sys.executable, str(settings.ROOT / "contracts" / "script" / "deploy.py")]
    env = os.environ.copy()
    if deploy_cmd is None:
        env["FORCE"] = "1"
    with maintenance(emit):
        if settings.NETWORK == "fuji":
            emit("deploy", "redeploying on fuji: costs gas, about 2 minutes, every address changes", status="info")
        before = _fingerprint()
        proc = subprocess.Popen(command, cwd=settings.ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            if line.strip():
                emit("deploy", line.rstrip(), status="info")
        if proc.wait() != 0:
            raise ScenarioError(f"{' '.join(command)} exited with {proc.returncode}")
        if _fingerprint() in (None, before):
            raise ScenarioError(f"{settings.DEPLOYMENTS_FILE.name} was not rewritten by the deployment")
        run_seed(emit, manage_maintenance=False)
        refund_safe(emit)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scenario.reset", description="Redeploy and seed again.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    emit = Emitter(args.run_id or new_run_id("reset", 0), args.json)
    return run_main(lambda: run_reset(emit), emit)


if __name__ == "__main__":
    sys.exit(main())
