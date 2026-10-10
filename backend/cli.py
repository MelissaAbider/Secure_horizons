"""Auditor CLI (TASKS.md T4 3.8).

python -m backend.cli verify <id>                          MATCH / MISMATCH + diffs; exit 0 / 1, 2 if unknown id
python -m backend.cli tamper <id> --field <path> --value <v>   demo only: edits the evidence file, keeps a .bak
python -m backend.cli restore <id>                         puts the .bak back
python -m backend.cli demo                                 dry-run replay of R1 at block 45201812 (jury demo)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from backend import evidence, settings


def _explorer_link(tx_hash: str) -> str | None:
    if settings.NETWORK != "fuji" or not tx_hash or tx_hash.startswith("0xdry"):
        return None
    try:
        from backend import chain

        return chain.explorer_tx(tx_hash)
    except Exception:  # noqa: BLE001
        return f"{settings.EXPLORER_URL}/tx/{tx_hash}"


def cmd_verify(decision_id: str) -> int:
    try:
        result = evidence.verify(decision_id)
    except LookupError as e:
        print(f"UNKNOWN {decision_id}: {e}")
        return 2
    print("MATCH" if result.match else "MISMATCH")
    print(f"decision: {result.decision_id}")
    print(f"record_hash: {result.stored_hash}")
    if result.anchored:
        print(f"anchored: yes (block {result.anchor_block}, tx {result.anchor_tx})")
        link = _explorer_link(result.anchor_tx)
        if link:
            print(f"explorer: {link}")
    else:
        print("anchored: no")
    for diff in result.diffs:
        print(f"- {diff}")
    return 0 if result.match else 1


def _parse_value(raw: str, old):
    if isinstance(old, str):
        return raw[1:-1] if len(raw) >= 2 and raw[0] == raw[-1] == '"' else raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def cmd_tamper(decision_id: str, field: str, raw_value: str) -> int:
    path = evidence.evidence_path(decision_id)
    if not path.exists():
        print(f"UNKNOWN {decision_id}: no evidence file {path}")
        return 2
    ev = json.loads(path.read_text(encoding="utf-8"))
    *parents, last = field.split(".")
    node = ev
    try:
        for part in parents:
            node = node[int(part)] if isinstance(node, list) else node[part]
        key = int(last) if isinstance(node, list) else last
        old = node[key]
    except (KeyError, IndexError, ValueError, TypeError):
        print(f"field not found: {field}")
        return 1
    new = _parse_value(raw_value, old)
    backup = path.with_name(path.name + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    node[key] = new
    path.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"TAMPERED {field}: {old} -> {new}")
    return 0


def cmd_restore(decision_id: str) -> int:
    path = evidence.evidence_path(decision_id)
    backup = path.with_name(path.name + ".bak")
    if not backup.exists():
        print(f"no backup for {decision_id}")
        return 1
    os.replace(backup, path)
    print(f"RESTORED {decision_id}")
    return 0


def cmd_demo() -> int:
    """Dry-run replay of the R1 critical alert at block 45201812 -> data/evidence/DEC-fuji-45201812-1.json.

    For the jury demo while the engine (T3) is not wired: no transaction, no AWS.
    """
    if not settings.DRY_RUN_ACTIONS:
        print("demo runs in dry-run only: set DRY_RUN_ACTIONS=true")
        return 1
    settings.ALERT_WEBHOOK_URL = settings.SNS_TOPIC_ARN = settings.EVIDENCE_BUCKET = ""
    from backend.executor import DryRunExecutor
    from backend.responder import Responder
    from backend.tests.test_t4_fixtures import FORGED_BLOCK, FakeStore, load_attack, r1_alert

    snap = load_attack(FORGED_BLOCK)
    decisions = Responder(FakeStore(), DryRunExecutor()).handle([r1_alert(snap)], snap)
    if not decisions:
        print("no decision")
        return 1
    d = decisions[0]
    print(f"DECISION {d.id} {d.matrix_cell} exposure=${d.exposure_usd:,.0f}")
    for i, a in enumerate(d.actions):
        print(f"  [{i}] {a.type}/{a.mode} {a.params or ''} {a.status} amount={a.amount}")
    print(f"record_hash: {d.record_hash}")
    print(f"evidence: {evidence.evidence_path(d.id)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify").add_argument("id")
    tamper = sub.add_parser("tamper")
    tamper.add_argument("id")
    tamper.add_argument("--field", required=True)
    tamper.add_argument("--value", required=True)
    sub.add_parser("restore").add_argument("id")
    sub.add_parser("demo")
    args = parser.parse_args(argv)
    if args.command == "demo":
        return cmd_demo()
    try:
        if args.command == "verify":
            return cmd_verify(args.id)
        if args.command == "tamper":
            return cmd_tamper(args.id, args.field, args.value)
        return cmd_restore(args.id)
    except LookupError as e:
        print(f"UNKNOWN {args.id}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
