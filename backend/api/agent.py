"""Allocation agent routes (dashboard and MCP server). Owner: agent.

GET  /agent/status                 loop on/off, model configured, dry-run, guaranteed rules
POST /agent/run                    one cycle now {"instructions": "..."}
POST /agent/loop                   {"enabled": true, "interval_s": 43200, "instructions": "..."}  (12 h; first cycle at once)
GET  /agent/cycles                 recorded cycles, newest first (tool calls, moves, summary, record_hash)
GET  /agent/moves                  every proposal and its verdict, newest first
POST /agent/moves/{id}/approve     a human signs a move above the threshold {"approver": "..."}
GET  /agent/tools                  the MCP tool list (names, descriptions, JSON schemas)
POST /agent/tools/{name}           call one tool (used by backend/mcp_server.py)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import agent_tools, autopilot

router = APIRouter(tags=["agent"])


class RunBody(BaseModel):
    instructions: str = Field(default="", max_length=autopilot.MAX_INSTRUCTIONS)


class LoopBody(BaseModel):
    enabled: bool
    interval_s: float = Field(default=12 * 3600, ge=15, le=24 * 3600)  # proposals every 12 h by default
    instructions: str = Field(default="", max_length=autopilot.MAX_INSTRUCTIONS)


class ApproveBody(BaseModel):
    approver: str = Field(min_length=1, max_length=80)


@router.get("/agent/status")
def agent_status() -> dict:
    return autopilot.status()


@router.post("/agent/run")
def agent_run(body: Optional[RunBody] = None) -> dict:
    cycle = autopilot.run_cycle((body or RunBody()).instructions, trigger="button")
    if "error" in cycle and "id" not in cycle:
        raise HTTPException(409, cycle["error"])
    return cycle


@router.post("/agent/loop")
def agent_loop(body: LoopBody) -> dict:
    return autopilot.start_loop(body.interval_s, body.instructions) if body.enabled else autopilot.stop_loop()


@router.get("/agent/cycles")
def agent_cycles() -> list[dict]:
    return autopilot.list_cycles()


@router.get("/agent/moves")
def agent_moves() -> list[dict]:
    return agent_tools.list_moves()


@router.post("/agent/moves/{move_id}/approve")
def agent_approve(move_id: str, body: ApproveBody) -> dict:
    try:
        return agent_tools.approve_move(move_id, body.approver)
    except KeyError as exc:
        raise HTTPException(404, f"unknown move {move_id}") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/agent/tools")
def agent_tools_list() -> list[dict]:
    return agent_tools.describe_tools()


@router.post("/agent/tools/{name}")
def agent_tool_call(name: str, args: Optional[dict] = None) -> dict:
    if name not in agent_tools.TOOLS:
        raise HTTPException(404, f"unknown tool {name}")
    return agent_tools.call_tool(name, args or {}, source="mcp")
