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


def _send(payload: dict, webhook_url: str, topic_arn: str, region: str, subject: str) -> None:
    if webhook_url:
        try:
            import httpx

            httpx.post(webhook_url, json=payload, timeout=3)
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
                                            settings.AWS_REGION, subject))
            thread.start()
            SENT_THREADS.append(thread)
            del SENT_THREADS[:-20]
    except Exception:  # noqa: BLE001
        logger.exception("notify failed for %s", decision.id)
    return channels
