"""Evidence: canonical JSON, hashes, evidence files, anchoring and verify (TASKS.md T4 3.5)."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import yaml
from eth_utils import keccak
from pydantic import BaseModel, ValidationError

from backend import settings
from backend.models import Alert, Decision, Snapshot, VerifyResult

logger = logging.getLogger("t4.evidence")

EVIDENCE_DIR: Path = settings.DATA_DIR / "evidence"  # tests monkeypatch it to tmp_path


def _plain(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, (list, tuple)):
        return [_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    return obj


def canonical_json(obj) -> str:
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def keccak_hex(text: str) -> str:
    return "0x" + keccak(text.encode("utf-8")).hex()


def inputs_hash(alerts: list[Alert], snapshot: Snapshot) -> str:
    return keccak_hex(canonical_json({"alerts": sorted(alerts, key=lambda a: a.id), "snapshot": snapshot}))


def record_hash(decision: Decision) -> str:
    return keccak_hex(canonical_json(decision.model_dump(mode="json",
                                                         exclude={"record_hash", "anchor_tx", "anchor_block"})))


def evidence_uri(decision_id: str) -> str:
    if settings.EVIDENCE_BUCKET:
        return f"s3://{settings.EVIDENCE_BUCKET}/evidence/{decision_id}.json"
    return f"file://data/evidence/{decision_id}.json"


def evidence_path(decision_id: str) -> Path:
    if not decision_id or "/" in decision_id or "\\" in decision_id or decision_id.startswith("."):
        raise LookupError(f"invalid decision id {decision_id!r}")
    return EVIDENCE_DIR / f"{decision_id}.json"


def save_evidence(decision_id: str, ev: dict) -> Path:
    """Write the evidence file (UTF-8, indent 2), then copy to S3 if EVIDENCE_BUCKET (failure logged, never raised)."""
    path = evidence_path(decision_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    if settings.EVIDENCE_BUCKET:
        try:
            import boto3

            boto3.client("s3", region_name=settings.AWS_REGION).upload_file(
                str(path), settings.EVIDENCE_BUCKET, f"evidence/{decision_id}.json")
        except Exception:  # noqa: BLE001
            logger.exception("S3 upload failed for %s", decision_id)
    return path


def write_evidence(decision: Decision, alerts: list[Alert], snapshot: Snapshot, playbook_yaml: str) -> Path:
    existing = load_local(decision.id)
    ev = {
        "decision": decision.model_dump(mode="json"),
        "inputs": {"alerts": [a.model_dump(mode="json") for a in sorted(alerts, key=lambda a: a.id)],
                   "snapshot": snapshot.model_dump(mode="json")},
        "playbook_yaml": playbook_yaml,
        "approvals": existing["approvals"] if existing else [],
    }
    return save_evidence(decision.id, ev)


def anchor_decision(decision: Decision, executor) -> Decision:
    res = executor.anchor(decision.record_hash, "decision", evidence_uri(decision.id))
    if res["status"] in ("executed", "skipped") and (res.get("tx_hash") or res.get("block_number")):
        return decision.model_copy(update={"anchor_tx": res.get("tx_hash"), "anchor_block": res.get("block_number")})
    logger.warning("anchor of %s not done: %s %s", decision.id, res["status"], res.get("note"))
    return decision.model_copy(update={"anchor_tx": None, "anchor_block": None})


def load_local(decision_id: str) -> dict | None:
    path = evidence_path(decision_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_evidence(decision_id: str) -> dict | None:
    ev = load_local(decision_id)
    if ev is not None or not settings.EVIDENCE_BUCKET:
        return ev
    try:
        import boto3

        obj = boto3.client("s3", region_name=settings.AWS_REGION).get_object(
            Bucket=settings.EVIDENCE_BUCKET, Key=f"evidence/{decision_id}.json")
        return json.loads(obj["Body"].read())
    except Exception:  # noqa: BLE001
        logger.exception("S3 read failed for %s", decision_id)
        return None


def anchors_path() -> Path:
    return EVIDENCE_DIR / "anchors.json"


def read_anchors() -> dict:
    path = anchors_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_anchors(anchors: dict) -> None:
    path = anchors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(anchors, indent=2), encoding="utf-8")


def _fmt_action(a) -> str:
    return f"{a.type}/{a.mode} {dict(sorted(a.params.items()))}"


def verify(decision_id: str) -> VerifyResult:
    """Replays a decision from its evidence file only (never the store). LookupError if unknown."""
    from backend.responder import plan_actions

    ev = load_evidence(decision_id)
    if ev is None:
        raise LookupError(f"no evidence for {decision_id}")
    try:
        d = Decision.model_validate(ev["decision"])
        alerts = [Alert.model_validate(a) for a in ev["inputs"]["alerts"]]
        snapshot = Snapshot.model_validate(ev["inputs"]["snapshot"])
        playbook_yaml = ev["playbook_yaml"]
    except (KeyError, TypeError, ValidationError) as e:
        stored = (ev.get("decision") or {}).get("record_hash") if isinstance(ev.get("decision"), dict) else None
        return VerifyResult(decision_id=decision_id, match=False, stored_hash=stored, anchored=False,
                            diffs=[f"evidence file is not valid: {type(e).__name__}: {str(e).splitlines()[0]}"])

    diffs: list[str] = []
    recomputed_inputs = inputs_hash(alerts, snapshot)
    if recomputed_inputs != d.inputs_hash:
        diffs.append(f"inputs_hash: stored {d.inputs_hash} != recomputed {recomputed_inputs}")

    playbook_version = "sha256:" + hashlib.sha256(playbook_yaml.encode("utf-8")).hexdigest()
    if playbook_version != d.playbook_version:
        diffs.append(f"playbook_version: stored {d.playbook_version} != recomputed {playbook_version}")
    replanned = plan_actions(alerts, snapshot, yaml.safe_load(playbook_yaml))
    if len(replanned) != len(d.actions):
        diffs.append(f"action count: stored {len(d.actions)} != replanned {len(replanned)}")
    for i, (stored, again) in enumerate(zip(d.actions, replanned)):
        if (stored.type, stored.mode, stored.params) != (again.type, again.mode, again.params):
            diffs.append(f"action[{i}]: stored {_fmt_action(stored)} != replanned {_fmt_action(again)}")

    recomputed = record_hash(d)
    if recomputed != d.record_hash:
        diffs.append(f"record_hash: stored {d.record_hash} != recomputed {recomputed}")

    anchored = False
    if d.record_hash and d.anchor_tx and d.anchor_tx.startswith("0xdry"):
        anchored = d.record_hash in read_anchors()
    elif d.record_hash:
        try:
            from backend import chain

            anchored = chain.registry().functions.anchoredAt(bytes.fromhex(d.record_hash[2:])).call() > 0
        except Exception as e:  # noqa: BLE001
            diffs.append(f"registry unreachable: {type(e).__name__}: {e}"[:200])
    if d.anchor_tx and not anchored:
        diffs.append(f"record_hash {d.record_hash} is not anchored on-chain")

    return VerifyResult(decision_id=d.id, match=not diffs, stored_hash=d.record_hash, recomputed_hash=recomputed,
                        anchored=anchored, anchor_tx=d.anchor_tx, anchor_block=d.anchor_block, diffs=diffs)
