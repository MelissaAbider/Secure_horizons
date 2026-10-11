"""MCP server of the allocation agent (stdio). Owner: agent.

Exposes the tools of backend/agent_tools.py (get_rules, get_markets, get_portfolio, get_alerts, propose_allocation)
to any MCP client (Claude Desktop, Claude Code, an agent framework). It is a thin proxy to the running backend
(SECURE_HORIZONS_API, default http://127.0.0.1:8000): the backend holds the chain state, the guard and the
teller path, so an MCP client gets exactly the same checks as the dashboard agent and never a key.

Run:  python -m backend.mcp_server        (make -f mk/agent.mk agent-mcp)
Claude Code:  claude mcp add secure-horizons -- <repo>/.venv/bin/python -m backend.mcp_server
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

API = os.environ.get("SECURE_HORIZONS_API", "http://127.0.0.1:8000").rstrip("/")

server: Server = Server("secure-horizons-treasury")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    async with httpx.AsyncClient(timeout=10) as client:
        tools = (await client.get(f"{API}/api/agent/tools")).raise_for_status().json()
    return [types.Tool(name=t["name"], description=t["description"], inputSchema=t["input_schema"],
                       annotations=types.ToolAnnotations(readOnlyHint=t["read_only"], destructiveHint=False))
            for t in tools]


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    async with httpx.AsyncClient(timeout=180) as client:  # a real Fuji move waits for its receipts
        resp = await client.post(f"{API}/api/agent/tools/{name}", json=arguments or {})
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"error": resp.text}
    return [types.TextContent(type="text", text=json.dumps(body, indent=2))]


async def _main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
