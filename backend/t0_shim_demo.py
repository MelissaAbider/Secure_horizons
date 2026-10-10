# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T4 + T5 demo through the T0 shim wiring: R1 critical at block 45201812, dry-run only.

python -m backend.t0_shim_demo   (make t4t5-demo)
Writes data/evidence/ and data/runtime/<NETWORK>/ (gitignored). No transaction, no AWS.
"""
from __future__ import annotations

import sys
from datetime import timedelta

from backend import evidence, settings


def main() -> int:
    if not settings.DRY_RUN_ACTIONS:
        print("demo runs in dry-run only: set DRY_RUN_ACTIONS=true")
        return 1
    settings.ALERT_WEBHOOK_URL = settings.SNS_TOPIC_ARN = settings.EVIDENCE_BUCKET = settings.BEDROCK_MODEL_ID = ""

    from backend import main as app_main
    from backend import responder
    from backend.store import Store
    from backend.tests.test_t4_fixtures import FORGED_BLOCK, load_attack
    from backend.tests.test_t5_factories import make_alert_r1

    store = Store()
    engine, _, _ = app_main.wire(store)
    snap = load_attack(FORGED_BLOCK)
    wall_clock = responder._now
    responder._now = lambda: snap.block_time + timedelta(seconds=2)  # scenario clock, like backend.cli demo
    try:
        engine.inject([make_alert_r1()], snap)
    finally:
        responder._now = wall_clock

    decisions = store.decisions()
    if not decisions:
        print("no decision")
        return 1
    d = decisions[0]
    print(f"DECISION {d.id} {d.matrix_cell} exposure=${d.exposure_usd:,.0f}")
    for i, a in enumerate(d.actions):
        print(f"  [{i}] {a.type}/{a.mode} {a.params or ''} {a.status} amount={a.amount}")
    for inc in store.incidents():
        print(f"INCIDENT {inc.id} {inc.status} saved=${inc.saved_usd:,.0f} exposure=${inc.exposure_usd:,.0f}")
    result = evidence.verify(d.id)
    print(f"VERIFY {'MATCH' if result.match else 'MISMATCH'} anchored={result.anchored}")
    for diff in result.diffs:
        print(f"- {diff}")
    return 0 if result.match else 1


if __name__ == "__main__":
    sys.exit(main())
