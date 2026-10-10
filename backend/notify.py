"""Notifications: log always, webhook and SNS in a background thread (TASKS.md T4 3.4). Never raises."""
from __future__ import annotations

import json
import logging
import threading

from backend import settings
from backend.models import Alert, Decision

logger = logging.getLogger("t4.notify")

SENT_THREADS: list[threading.Thread] = []  # last background sends, joined by tests


def build_payload(decision: Decision, alerts: list[Alert]) -> dict:
    summary = (f"[{decision.severity.upper()}] {decision.id} on {decision.network} block {decision.block_number}: "
               f"{decision.rationale}")
    return {
        "text": summary,
        "content": summary,
        "decision_id": decision.id,
        "severity": decision.severity,
        "network": decision.network,
        "block_number": decision.block_number,
        "exposure_usd": decision.exposure_usd,
        "matrix_cell": decision.matrix_cell,
        "alerts": [{"id": a.id, "rule_id": a.rule_id, "severity": a.severity, "explanation": a.explanation}
                   for a in alerts],
        "actions": [{"type": a.type, "mode": a.mode, "status": a.status} for a in decision.actions],
    }


DISCORD_COLORS = {"critical": 0xE53935, "high": 0xF4511E, "warning": 0xFFB300, "info": 0x607D8B}
_DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}
_ACTION_ICON = {"executed": "✅", "pending_approval": "⏳", "approved": "✅", "skipped": "⏭️", "failed": "❌",
                "rejected": "🚫", "planned": "•"}


def is_discord_webhook(url: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host in {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}


def _amount(base: str | None, asset: str | None) -> str:
    if not base or not asset:
        return ""
    value = int(base) / 10 ** _DECIMALS.get(asset, 18)
    return f" {value:,.0f} {asset}" if value == int(value) else f" {value:,.2f} {asset}"


def build_discord_payload(decision: Decision, alerts: list[Alert]) -> dict:
    """Discord webhook message (content + one embed), within Discord limits
    (title 256, description 4096, 25 fields, field value 1024, content 2000)."""
    lines = []
    for i, a in enumerate(decision.actions):
        p = a.params or {}
        where = f" · {p.get('deployment_id')}" if p.get("deployment_id") else ""
        lines.append(f"{_ACTION_ICON.get(a.status, '•')} `{i}` **{a.type}**{where}{_amount(a.amount, p.get('asset'))}"
                     f" — {a.mode}, {a.status}")
    fields = [
        {"name": "Exposure", "value": f"{decision.exposure_usd:,.0f} USD", "inline": True},
        {"name": "Withdrawable", "value": f"{decision.withdrawable_usd:,.0f} USD", "inline": True},
        {"name": "Network / block", "value": f"{decision.network} · {decision.block_number:,}", "inline": True},
        {"name": "Matrix cell", "value": f"`{decision.matrix_cell}`", "inline": False},
        {"name": "Actions", "value": "\n".join(lines)[:1024] or "none", "inline": False},
    ]
    if decision.record_hash:
        fields.append({"name": "Evidence", "value": f"record_hash `{decision.record_hash}`\n"
                       f"verify: `make verify ID={decision.id}`"[:1024], "inline": False})
    return {
        "username": "Secure Horizons",
        "content": f"🚨 **[{decision.severity.upper()}] {decision.id}** — {decision.rationale}"[:2000],
        "embeds": [{
            "title": (alerts[0].title if alerts else decision.id)[:256],
            "description": "\n".join(f"**{a.rule_id}** ({a.severity}) {a.explanation}" for a in alerts)[:4096],
            "color": DISCORD_COLORS.get(decision.severity, 0x607D8B),
            "fields": fields[:25],
            "footer": {"text": f"{decision.id} · rules {decision.rules_version[:19]} · "
                               f"playbook {decision.playbook_version[:19]}"[:2048]},
            "timestamp": decision.created_at.isoformat().replace("+00:00", "Z"),
        }],
        "allowed_mentions": {"parse": []},  # alert text can never ping @everyone
    }


def post_webhook(url: str, payload: dict) -> int:
    """POST a payload and return the HTTP status (Discord answers 204). Raises on network errors."""
    import httpx
    return httpx.post(url, json=payload, timeout=5).status_code


def _send(payload: dict, webhook_url: str, topic_arn: str, region: str, subject: str,
          discord_payload: dict | None = None) -> None:
    if webhook_url:
        try:
            body = discord_payload if discord_payload and is_discord_webhook(webhook_url) else payload
            status = post_webhook(webhook_url, body)
            if status >= 300:
                logger.warning("webhook answered HTTP %s", status)
        except Exception:  # noqa: BLE001
            logger.exception("webhook notification failed")
    if topic_arn:
        try:
            import boto3

            boto3.client("sns", region_name=region).publish(TopicArn=topic_arn, Subject=subject,
                                                            Message=json.dumps(payload))
        except Exception:  # noqa: BLE001
            logger.exception("SNS notification failed")


def notify(decision: Decision, alerts: list[Alert]) -> list[str]:
    """Returns the configured channels: ["log"] + "webhook" + "sns"."""
    channels = ["log"]
    try:
        webhook_url, topic_arn = settings.ALERT_WEBHOOK_URL, settings.SNS_TOPIC_ARN
        if webhook_url:
            channels.append("webhook")
        if topic_arn:
            channels.append("sns")
        logger.warning("NOTIFY %s %s exposure=$%.0f %s", decision.id, decision.severity, decision.exposure_usd,
                       decision.rationale)
        if webhook_url or topic_arn:
            subject = f"[{decision.severity.upper()}] {decision.id}"[:100]
            thread = threading.Thread(target=_send, daemon=True,
                                      args=(build_payload(decision, alerts), webhook_url, topic_arn,
                                            settings.AWS_REGION, subject, build_discord_payload(decision, alerts)))
            thread.start()
            SENT_THREADS.append(thread)
            del SENT_THREADS[:-20]
    except Exception:  # noqa: BLE001
        logger.exception("notify failed for %s", decision.id)
    return channels


def main(argv: list[str] | None = None) -> int:
    """make discord-test: build the Discord message for the R1 scenario decision (DEC-fuji-45201812-1),
    write it to data/notifications/<id>.discord.json and post it to ALERT_WEBHOOK_URL if set.
    The webhook URL is a secret: it is never printed."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m backend.notify")
    parser.add_argument("--no-send", action="store_true", help="only write the JSON file")
    args = parser.parse_args(argv)
    from backend.tests.test_t5_factories import make_alert_r1, make_decision_r1

    decision, alerts = make_decision_r1(), [make_alert_r1()]
    payload = build_discord_payload(decision, alerts)
    out = settings.DATA_DIR / "notifications" / f"{decision.id}.discord.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    url = settings.ALERT_WEBHOOK_URL
    if args.no_send:
        return 0
    if not url:
        print("ALERT_WEBHOOK_URL is empty: add it to .env to post to Discord")
        return 1
    if not is_discord_webhook(url):
        print("ALERT_WEBHOOK_URL is not a discord.com webhook")
        return 1
    try:
        status = post_webhook(url, payload)
    except Exception as e:  # noqa: BLE001
        print(f"webhook error: {type(e).__name__}")
        return 1
    print(f"Discord answered HTTP {status} ({'OK' if status in (200, 204) else 'FAILED'})")
    return 0 if status in (200, 204) else 1


if __name__ == "__main__":
    raise SystemExit(main())
