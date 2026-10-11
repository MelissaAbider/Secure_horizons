# Allocation agent (MCP + Bedrock)

Claude Opus 5.5 on Bedrock picks the markets on its own by calling MCP tools. It proposes; the platform re-reads the
chain and the guaranteed rules, then executes through the teller window (sealed list, back to the Safe), asks a human
to sign, or refuses. The agent holds no key (INVARIANTS 1-4, 7).

| Piece | File |
|---|---|
| Tools and guard (`check_move`, pure) | `backend/agent_tools.py` |
| Guaranteed rules (40 % per protocol, signature above 100,000 USD, 2 moves per cycle) | `backend/config/agent_rules.yaml` |
| Agent loop (Bedrock Converse tool use, fallback planner, CYC records) | `backend/autopilot.py` |
| HTTP routes `/api/agent/*` | `backend/api/agent.py` |
| MCP server (stdio, proxies the running backend) | `backend/mcp_server.py` |
| Dashboard panel (Setup page, once monitoring is live) | `frontend/src/components/AgentAutopilot.tsx` |

## MCP tools

| Tool | Kind | What it returns or does |
|---|---|---|
| `get_rules` | read | caps, signature threshold, alert policy |
| `get_markets` | read | per market at the latest block: APY, utilization, liquidity, frozen/paused, sealed or not |
| `get_portfolio` | read | Safe idle balances and positions (whole tokens), USD per protocol |
| `get_alerts` | read | active high/critical alerts, open incidents |
| `propose_allocation` | action | one deposit or withdraw; answer: executed, simulated, awaiting_signature or refused with reasons |

Connect any MCP client to the running backend: `claude mcp add secure-horizons -- .venv/bin/python -m backend.mcp_server`
(`SECURE_HORIZONS_API` overrides `http://127.0.0.1:8000`).

## Run

- `.env`: `BEDROCK_MODEL_ID` (the Opus 5.5 inference profile enabled on the account), `AWS_REGION=us-east-1`, AWS
  credentials from the instance role or the usual AWS variables. Empty model id: deterministic fallback planner.
- `DRY_RUN_ACTIONS=true` (default): approved moves are simulated. Without a connected Safe, a labelled paper treasury
  (`paper_portfolio` in the rules file) is used so the agent can be tried without keys. `false`: real Fuji moves.
- Dashboard: Setup page → "Let the agent manage" (one cycle) or "Autopilot every 30s".
- Bedrock: read timeout 30 s, no retry, at most 1 request per second; an error before the first tool call falls back.

Every cycle is written to `data/evidence/CYC-<block>-<n>.json` with its `record_hash`.
