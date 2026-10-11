"""Discord fraud summary (format from the T4/T5 branch, content from our live data). Owner: T4.

One message per incident, sent when the fraud is detected: a short content line plus one embed (colour by severity,
the alert explanation, exposure and withdrawable value read on-chain, the incident and its DORA status). Discord limits are respected
(content 2000, title 256, description 4096, 25 fields, field value 1024) and the message can never ping anyone.
The webhook URL is a secret (.env ALERT_WEBHOOK_URL): it is never printed or logged.
"""
from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

from backend import settings
from backend.models import Alert, Incident, Snapshot

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
DISCORD_COLORS = {"critical": 0xE53935, "high": 0xF4511E, "warning": 0xFFB300, "info": 0x607D8B}
_ICON = {"critical": "🚨", "high": "⚠️", "warning": "🔶", "info": "ℹ️"}


def is_discord_webhook(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}


def _usd(value: float) -> str:
    return f"{value:,.0f} USD"


def _vault_position_values(snapshot: Snapshot, deployments: set[str]) -> tuple[float, float]:
    """(value, withdrawable now) of the vault positions in these deployments, from the snapshot (USD)."""
    vault = snapshot.vault.address.lower()
    rows = [p for p in snapshot.positions if p.wallet.lower() == vault and (not deployments or p.deployment_id in deployments)]
    return sum(p.value_usd for p in rows), sum(p.withdrawable_usd for p in rows)


def scope(alerts: list[Alert]) -> set[str]:
    """Deployments concerned: the alerts' own, plus those a global alert lists as exposed (R1 metrics)."""
    out = {a.deployment_id for a in alerts if a.deployment_id}
    for a in alerts:
        out |= {d for d in str(a.metrics.get("exposed_deployments", "")).split(",") if d}
    return out


def build_alert_payload(alerts: list[Alert], snapshot: Snapshot, incident: Optional[Incident] = None) -> dict:
    top = max(alerts, key=lambda a: (SEVERITY_RANK[a.severity], a.exposure_usd))
    deployments = scope(alerts)
    value, withdrawable = _vault_position_values(snapshot, deployments)
    where = ", ".join(sorted(deployments)) or "all deployments accepting rsETH"
    block = f"{snapshot.network} · {snapshot.block_number:,}"
    if snapshot.network == "fuji":
        block = f"[{block}]({settings.EXPLORER_URL}/block/{snapshot.block_number})"
    fields = [
        {"name": "Exposure", "value": _usd(max(a.exposure_usd for a in alerts)), "inline": True},
        {"name": "Withdrawable now", "value": f"{_usd(withdrawable)} of {_usd(value)}", "inline": True},
        {"name": "Network / block", "value": block, "inline": True},
        {"name": "Scope", "value": where[:1024], "inline": False},
    ]
    if incident is not None and incident.dora is not None:
        d = incident.dora
        fields.append({"name": "Incident", "value": (
            f"`{incident.id}` · {incident.status} · DORA: **{'major' if d.is_major else 'not major'}** "
            f"(thresholds {', '.join(t.split(' ')[0] for t in d.thresholds_met) or 'none'})\n"
            f"Initial notification due {d.deadlines.initial_notification_due.strftime('%Y-%m-%d %H:%M UTC')} · "
            f"DORA draft PDF attached")[:1024], "inline": False})
    fields.append({"name": "Response", "value": "Detection only: no automated withdrawal. Review the positions.",
                   "inline": False})
    return {
        "username": "Secure Horizons",
        "content": (f"{_ICON[top.severity]} **Fraud detected: {top.title}** · treasury exposure "
                    f"{_usd(max(a.exposure_usd for a in alerts))}" + (" · DORA draft attached" if incident else ""))[:2000],
        "embeds": [{
            "title": f"Fraud detected: {top.title}"[:256],
            "description": "\n".join(f"**{a.rule_id}** ({a.severity}) {a.explanation}" for a in alerts)[:4096],
            "color": DISCORD_COLORS[top.severity],
            "fields": fields[:25],
            "footer": {"text": f"{', '.join(a.id for a in alerts)} · rules {top.rules_version[:19]}"[:2048]},
            "timestamp": top.detected_at.isoformat().replace("+00:00", "Z"),
        }],
        "allowed_mentions": {"parse": []},  # alert text can never ping @everyone
    }


def post_webhook(url: str, payload: dict, attachment: Optional[tuple[str, bytes]] = None) -> int:
    """POST the message (with an optional file) and return the HTTP status (Discord answers 200 or 204)."""
    import httpx

    if attachment is None:
        return httpx.post(url, json=payload, timeout=10).status_code
    name, content = attachment
    return httpx.post(url, data={"payload_json": json.dumps(payload)},
                      files={"files[0]": (name, content, "application/pdf")}, timeout=20).status_code
