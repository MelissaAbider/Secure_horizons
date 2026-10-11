"""Response routes (T4): withdraw buttons on the Discord fraud alert. Owner: T4.

GET  /decisions              response decisions in the store (none in detection-only mode, TASKS.md 2.9)
POST /discord/interactions   Discord calls it on a button click (Interactions Endpoint URL, signed with Ed25519)
GET  /discord/actions        every click and its outcome, newest first (dashboard)
GET  /discord/config         whether buttons can be sent and clicks verified (no secret is returned)
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException, Request

from backend import discord_actions
from backend.models import Decision

router = APIRouter(tags=["response"])


@router.get("/decisions", response_model=list[Decision])
def decisions():
    from backend.store import store

    return store.decisions()


@router.post("/discord/interactions")
async def discord_interactions(request: Request) -> dict:
    body = await request.body()
    if not discord_actions.verify_signature(os.environ.get("DISCORD_PUBLIC_KEY", "").strip(),
                                            request.headers.get("X-Signature-Ed25519", ""),
                                            request.headers.get("X-Signature-Timestamp", ""), body):
        raise HTTPException(401, "invalid request signature")
    try:
        interaction = json.loads(body)
    except ValueError as exc:
        raise HTTPException(400, "invalid JSON") from exc
    return discord_actions.handle(interaction)


@router.get("/discord/actions")
def discord_action_list() -> list[dict]:
    return discord_actions.list_actions()


@router.get("/discord/config")
def discord_config() -> dict:
    return {"buttons": discord_actions.bot_configured(),
            "interactions": bool(os.environ.get("DISCORD_PUBLIC_KEY", "").strip()),
            "allowed_users": len(discord_actions.allowed_users())}
