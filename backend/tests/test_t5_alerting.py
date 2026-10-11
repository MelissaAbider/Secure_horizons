"""Detection-only alerting: Discord payload, incident, DORA classification and PDF. No network, no chain."""
import json

import pytest

from backend import settings
from backend.alerting import Alerting
from backend.models import Alert, Snapshot
from backend.notify import build_alert_payload
from backend.store import Store

WEBHOOK = "https://discord.com/api/webhooks/1/test"


def snapshots() -> dict[int, Snapshot]:
    lines = (settings.FIXTURES_DIR / "snapshots_attack.jsonl").read_text().splitlines()
    return {s.block_number: s for s in (Snapshot.model_validate_json(line) for line in lines if line.strip())}


def r1() -> Alert:
    return Alert.model_validate(json.loads((settings.FIXTURES_DIR / "alerts.json").read_text())[0])


def later(rule_id: str, severity: str, block: int, deployment: str, asset: str, exposure: float) -> Alert:
    a = r1()
    return a.model_copy(update={"id": f"ALT-fuji-{block}-{rule_id}-{deployment}-{asset}", "rule_id": rule_id,
                                "severity": severity, "block_number": block, "deployment_id": deployment,
                                "asset": asset, "exposure_usd": exposure, "title": f"{rule_id} on {deployment}",
                                "explanation": f"{rule_id} explanation."})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", WEBHOOK)
    posts = []
    alerting = Alerting(Store(runtime_dir=tmp_path / "runtime"), post=lambda url, payload, file: posts.append(
        {"url": url, "payload": payload, "file": file}) or 204)
    return alerting, posts, tmp_path


def test_payload_format_and_limits():
    snap = snapshots()[45201812]
    payload = build_alert_payload([r1()], snap)
    embed = payload["embeds"][0]
    assert payload["allowed_mentions"] == {"parse": []} and payload["username"] == "Secure Horizons"
    assert embed["color"] == 0xE53935 and payload["content"].startswith("🚨 **[CRITICAL]")
    assert len(payload["content"]) <= 2000 and len(embed["title"]) <= 256 and len(embed["description"]) <= 4096
    names = [f["name"] for f in embed["fields"]]
    assert names[:4] == ["Exposure", "Withdrawable now", "Network / block", "Scope"]
    assert "testnet.snowtrace.io/block/45201812" in embed["fields"][2]["value"]
    assert embed["fields"][0]["value"] == "1,325,000 USD"


def test_incident_dora_and_discord_flow(env):
    alerting, posts, data = env
    snaps = snapshots()
    alerting.handle([r1()], snaps[45201812])
    incident = alerting.handle([later("R3_LIQUIDITY_DRAIN", "high", 45201826, "lend-eth", "WETH", 375_000)], snaps[45201826])
    incident = alerting.handle([later("R5_CONTAINMENT", "critical", 45201878, "lend-eth", "rsETH", 775_000)], snaps[45201878])

    assert incident.id.startswith("INC-20261011-") and incident.status == "open"
    assert incident.exposure_usd == 1_325_000 and incident.saved_usd == 0 and incident.at_risk_usd == 1_325_000
    assert len(incident.alert_ids) == 3
    d = incident.dora
    assert d.is_major and [t.split(" ")[0] for t in d.thresholds_met] == ["9(1)", "9(4)", "9(6)"]
    assert d.aware_at == r1().detected_at
    assert "No automated withdrawal was executed" in d.report_markdown
    assert "MockBridge" in d.report_markdown or "rsETH bridge" in d.report_markdown
    pdf = (data / "reports" / f"{incident.id}.pdf").read_bytes()
    assert pdf.startswith(b"%PDF")

    assert [p["file"] is not None for p in posts] == [True, False, True]  # PDF on opening and on containment
    assert posts[0]["file"][0] == f"{incident.id}-DORA-draft.pdf" and posts[0]["file"][1].startswith(b"%PDF")
    assert all(p["url"] == WEBHOOK for p in posts)
    assert any(f["name"] == "Incident" for f in posts[1]["payload"]["embeds"][0]["fields"])
    sent = [e for e in incident.timeline if e.kind == "action"]
    assert len(sent) == 3 and sent[0].text.endswith("(DORA draft attached)")


def test_warnings_are_not_sent_and_high_alone_opens_no_incident(env):
    alerting, posts, _ = env
    snap = snapshots()[45201826]
    assert alerting.handle([later("R2_COLLATERAL_SURGE", "warning", 45201826, "lend-eth", "rsETH", 1)], snap) is None
    assert posts == []
    assert alerting.handle([later("R3_LIQUIDITY_DRAIN", "high", 45201826, "lend-eth", "WETH", 375_000)], snap) is None
    assert len(posts) == 1 and posts[0]["file"] is None
    assert alerting.store.incidents() == []


def test_no_webhook_still_writes_the_dora_draft(env, monkeypatch):
    alerting, posts, data = env
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "")
    incident = alerting.handle([r1()], snapshots()[45201812])
    assert posts == [] and (data / "reports" / f"{incident.id}.pdf").exists()
    assert not [e for e in incident.timeline if e.kind == "action"]
    assert "- No automated action executed." in incident.dora.report_markdown


def test_failed_webhook_is_not_recorded_as_sent(env):
    alerting, _, _ = env
    alerting.post = lambda url, payload, file: 500
    incident = alerting.handle([r1()], snapshots()[45201812])
    assert not [e for e in incident.timeline if e.kind == "action"]
