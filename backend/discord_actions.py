"""Withdraw buttons on the Discord fraud alert. Owner: T4.

The fraud summary carries one button per sealed integration in the alert scope ("Withdraw WETH from lend-eth") plus
"Withdraw all". A click reaches POST /api/discord/interactions; it is accepted only if:
- the Ed25519 signature of Discord is valid (DISCORD_PUBLIC_KEY, the application's public key);
- the clicking Discord user is in DISCORD_ALLOWED_USER_IDS (empty list: every click is refused);
- the button id is one of ours (sh:withdraw:<protocol>:<asset> or sh:withdraw:all): free text never maps to an action.

The withdrawal goes through the same path as the dashboard (POST /api/safe/allocate): the teller-window module,
inside the sealed list, back to the Safe. Funds never leave the Safe, and no new key is involved.
With DRY_RUN_ACTIONS=true (default) nothing is sent: the action is recorded as simulated.
Every click (accepted, refused, executed, failed) is kept for the dashboard (GET /api/discord/actions).

Sending buttons needs a bot (incoming webhooks cannot carry interactive buttons):
DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID in .env. Without them the alert goes out through ALERT_WEBHOOK_URL, without buttons.
Secrets (bot token, interaction tokens) are never printed or logged.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from backend import settings
from backend.models import Alert

log = logging.getLogger("backend.discord_actions")

API = "https://discord.com/api/v10"
PREFIX = "sh:withdraw:"
ALL = "all"
ASSETS = ("USDC", "WETH")
_ID = re.compile(r"^sh:withdraw:(all|lend-[a-z]+:(USDC|WETH))$")
EPHEMERAL = 64
MAX_KEPT = 200

_LOCK = threading.Lock()
ACTIONS: list[dict[str, Any]] = []  # oldest first
_SEEN: set[str] = set()  # interaction ids already handled (Discord may retry)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def bot_configured() -> bool:
    return bool(_env("DISCORD_BOT_TOKEN") and _env("DISCORD_CHANNEL_ID"))


def allowed_users() -> set[str]:
    return {u.strip() for u in _env("DISCORD_ALLOWED_USER_IDS").split(",") if u.strip()}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- buttons on the alert ----------

def _sealed_integrations() -> Optional[list[str]]:
    try:
        from sealed import safe as S

        return list(S.load_state()["sealed"]["integrations"])
    except Exception:  # no Safe connected or nothing sealed yet
        return None


def integrations_for(alerts: list[Alert]) -> list[str]:
    """Sealed integrations in the alert scope; without a sealed list, every asset of the scoped deployments."""
    from backend import notify

    scope = notify.scope(alerts)
    sealed = _sealed_integrations()
    if sealed is not None:
        return sorted(i for i in sealed if not scope or i.split(":")[0] in scope)
    return sorted(f"{d}:{a}" for d in scope for a in ASSETS)


def components(alerts: list[Alert]) -> list[dict]:
    """Discord action rows: one button per integration (at most 4 rows of 5), then "Withdraw all"."""
    buttons = [{"type": 2, "style": 2, "label": f"Withdraw {i.split(':')[1]} from {i.split(':')[0]}"[:80],
                "custom_id": PREFIX + i} for i in integrations_for(alerts)[:20]]
    rows = [{"type": 1, "components": buttons[k:k + 5]} for k in range(0, len(buttons), 5)]
    if buttons:
        rows.append({"type": 1, "components": [{"type": 2, "style": 4, "label": "Withdraw all to the Safe",
                                                 "custom_id": PREFIX + ALL}]})
    return rows


def with_buttons(payload: dict, alerts: list[Alert]) -> dict:
    """The webhook payload as a bot message: buttons added, webhook-only fields dropped."""
    out = {k: v for k, v in payload.items() if k not in ("username", "avatar_url")}
    out["components"] = components(alerts)
    if out["components"]:
        embeds = [dict(e) for e in out.get("embeds", [])]
        for e in embeds:
            e["fields"] = [dict(f, value="Withdraw buttons below: allowed members only, funds go back to the Safe "
                                         "through the sealed list.") if f.get("name") == "Response" else f
                           for f in e.get("fields", [])]
        out["embeds"] = embeds
    return out


def post_bot(payload: dict, attachment: Optional[tuple[str, bytes]] = None) -> int:
    """Send the message to DISCORD_CHANNEL_ID as the bot; returns the HTTP status."""
    import httpx

    url = f"{API}/channels/{_env('DISCORD_CHANNEL_ID')}/messages"
    headers = {"Authorization": f"Bot {_env('DISCORD_BOT_TOKEN')}"}
    if attachment is None:
        return httpx.post(url, json=payload, headers=headers, timeout=10).status_code
    name, content = attachment
    return httpx.post(url, headers=headers, data={"payload_json": json.dumps(payload)},
                      files={"files[0]": (name, content, "application/pdf")}, timeout=20).status_code


# ---------- incoming clicks ----------

def verify_signature(public_key_hex: str, signature_hex: str, timestamp: str, body: bytes) -> bool:
    """Discord signs timestamp + raw body with the application's Ed25519 key."""
    if not (public_key_hex and signature_hex and timestamp):
        return False
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey

        VerifyKey(bytes.fromhex(public_key_hex)).verify(timestamp.encode() + body, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError):
        return False


def _reply(text: str, ephemeral: bool = False) -> dict:
    data: dict[str, Any] = {"content": text[:2000], "allowed_mentions": {"parse": []}}
    if ephemeral:
        data["flags"] = EPHEMERAL
    return {"type": 4, "data": data}


def _persist(action: dict) -> None:
    """Append the action as it is now to data/runtime/<network>/discord_actions.jsonl (last line per id wins)."""
    try:
        path = settings.runtime_dir() / "discord_actions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(action) + "\n")
    except OSError:
        log.warning("discord action not written to disk")


def _keep(action: dict) -> dict:
    with _LOCK:
        ACTIONS.append(action)
        del ACTIONS[:-MAX_KEPT]
    _persist(action)
    return action


def list_actions() -> list[dict]:
    """Every Discord click, newest first."""
    with _LOCK:
        return [dict(a) for a in reversed(ACTIONS)]


def reset() -> None:
    with _LOCK:
        ACTIONS.clear()
        _SEEN.clear()


def _withdraw(integration: str) -> dict:
    """One withdrawal of the whole position through the teller window (same guard as the dashboard)."""
    from fastapi import HTTPException

    from backend.api import safe
    from sealed import live

    try:
        record = safe._guarded(lambda: live.allocate(integration, "withdraw", "max"))
    except HTTPException as exc:
        return {"integration": integration, "verdict": "FAILED", "detail": str(exc.detail), "txs": []}
    except Exception as exc:  # chain unreachable, Safe not connected
        return {"integration": integration, "verdict": "FAILED", "detail": type(exc).__name__, "txs": []}
    return {"integration": integration, "verdict": record.get("verdict"), "detail": record.get("detail"),
            "txs": record.get("txs", [])}


def execute(action: dict, run: Callable[[str], dict] = _withdraw) -> dict:
    """Run the withdrawals of an accepted click and fill in its outcome."""
    if settings.DRY_RUN_ACTIONS:
        results = [{"integration": i, "verdict": "SIMULATED", "detail": "DRY_RUN_ACTIONS=true: nothing sent",
                    "txs": []} for i in action["integrations"]]
        status = "simulated"
    else:
        results = [run(i) for i in action["integrations"]]
        ok = [r["verdict"] == "EXECUTED" for r in results]
        status = "executed" if all(ok) else "partial" if any(ok) else "failed"
    with _LOCK:
        action.update(status=status, results=results, finished_at=_now())
    _persist(action)
    log.warning("DISCORD_ACTION %s %s by %s -> %s", action["id"], action["button"], action["user"], status)
    return action


def summary(action: dict) -> str:
    lines = [f"**{action['label']}** requested by {action['user']}: {action['status']}"]
    explorer = settings.EXPLORER_URL if settings.NETWORK == "fuji" else ""
    for r in action.get("results", []):
        txs = ", ".join(f"[{t[:10]}…]({explorer}/tx/{t})" if explorer else f"`{t[:10]}…`" for t in r["txs"])
        lines.append(f"- {r['integration']}: {r['verdict']}" + (f" · {txs}" if txs else "")
                     + (f" · {r['detail']}" if r.get("detail") else ""))
    lines.append("Shown on the dashboard (Live monitoring · Discord).")
    return "\n".join(lines)


def _follow_up(application_id: str, token: str, text: str) -> None:
    """Replace the 'in progress' answer with the outcome (the interaction token is valid 15 minutes)."""
    import httpx

    try:
        httpx.patch(f"{API}/webhooks/{application_id}/{token}/messages/@original",
                    json={"content": text[:2000], "allowed_mentions": {"parse": []}}, timeout=10)
    except Exception as exc:
        log.warning("Discord follow-up failed (%s)", type(exc).__name__)


def _background(action: dict, application_id: str, token: str) -> None:
    execute(action)
    _follow_up(application_id, token, summary(action))


def handle(interaction: dict, start: Callable[[Callable[[], None]], None] = lambda fn: threading.Thread(
        target=fn, daemon=True).start()) -> dict:
    """Answer one verified interaction. Execution runs in the background; Discord gets an answer within 3 s."""
    kind = interaction.get("type")
    if kind == 1:  # PING when the endpoint URL is saved in the Developer Portal
        return {"type": 1}
    if kind != 3:
        return _reply("Unsupported interaction.", ephemeral=True)

    custom_id = str((interaction.get("data") or {}).get("custom_id", ""))
    who = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    user_id, user = str(who.get("id", "")), str(who.get("username", "unknown"))
    match = _ID.match(custom_id)
    if not match:
        return _reply("Unknown button.", ephemeral=True)

    with _LOCK:
        if interaction.get("id") in _SEEN:
            return _reply("Already handled.", ephemeral=True)
        _SEEN.add(str(interaction.get("id")))
    target = match.group(1)
    if target == ALL:
        integrations = _sealed_integrations() or []
        label = "Withdraw all to the Safe"
    else:
        integrations = [target]
        label = f"Withdraw {target.split(':')[1]} from {target.split(':')[0]}"
    action = {"id": f"DSC-{len(ACTIONS) + 1:04d}", "at": _now(), "user": user, "user_id": user_id,
              "button": custom_id, "label": label, "integrations": integrations, "status": "pending",
              "results": [], "finished_at": None, "network": settings.NETWORK, "dry_run": settings.DRY_RUN_ACTIONS}

    if user_id not in allowed_users():
        _keep({**action, "status": "refused", "results": [], "reason": "user not in DISCORD_ALLOWED_USER_IDS"})
        return _reply("Refused: your Discord account is not allowed to move treasury funds.", ephemeral=True)
    if not integrations:
        _keep({**action, "status": "refused", "reason": "no sealed integration to withdraw from"})
        return _reply("Refused: no sealed integration to withdraw from.", ephemeral=True)

    _keep(action)
    start(lambda: _background(action, str(interaction.get("application_id", "")), str(interaction.get("token", ""))))
    mode = " (dry run: nothing is sent)" if settings.DRY_RUN_ACTIONS else ""
    return _reply(f"⏳ **{label}** requested by {user}{mode}: withdrawing through the teller window, back to the Safe…")
