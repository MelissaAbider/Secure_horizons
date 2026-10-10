# Contract: API, commands, fixtures

> Light version of `TASKS.md` (full detail there). Same numbering, so a reference like "2.7" means the same thing in both.

### 2.9 HTTP API (prefix `/api`, port 8000)

While `USE_FIXTURES=true`, each route returns the listed fixture (the T0 skeleton already does this). Each owning task then plugs in the real data.

| Method and route | Parameters | Response | Owner | Fixture |
|---|---|---|---|---|
| `GET /api/health` | — | `Health` | T3 | `health.json` |
| `GET /api/state` | — | `StateResponse` | T3 | `state.json` |
| `GET /api/series` | `deployment_id`, `asset`, `limit` (≤ 2000, default 300) | `SeriesPoint[]` (chronological order) | T3 | `series.json` |
| `GET /api/alerts` | `since_block` (default 0) | `Alert[]` (most recent first) | T3 | `alerts.json` |
| `GET /api/decisions` | — | `Decision[]` (most recent first) | T4 | `decisions.json` |
| `POST /api/decisions/{id}/approve` | `{"action_index": int, "approver": str, "approve": bool}` | `Decision` (the action becomes `approved` then `executed`, or `rejected`) | T4 | — |
| `POST /api/verify/{decision_id}` | — | `VerifyResult` | T4 | `verify.json` |
| `GET /api/incidents` | — | `Incident[]` | T5 | `incident.json` (list of one element) |
| `GET /api/incidents/{id}` | — | `Incident` | T5 | `incident.json` |
| `GET /api/incidents/{id}/report.md` | — | markdown text | T5 | field `dora.report_markdown` |
| `POST /api/incidents/{id}/submit` | `{"submitted_by": str}` | `Incident` (`dora.submitted = true`) | T5 | — |
| `GET /api/dependencies` | — | `Dependency[]` | T5 | `dependencies.json` |
| `POST /api/demo/attack` | `{"seed": int \| null, "variant": "default" \| "slow" \| "usdc"}`; `seed = null`: the backend draws a random seed and returns it; `seed = 0`: default parameters, no randomness | `DemoRun` (started in the background) | T2 | `demo_run.json` |
| `POST /api/demo/reset` | — | `DemoRun` (redeploys, re-seeds, empties the store) | T2 | `demo_run.json` |
| `GET /api/demo/runs/{run_id}` | — | `DemoRun` | T2 | `demo_run.json` |
| `GET /api/metrics` | — | `EvalMetrics` (reads `data/eval/metrics.json`, otherwise the fixture) | T7 | `metrics.json` |

Errors, always with `{"detail": "..."}`:

| Code | When |
|---|---|
| 404 | unknown id |
| 400 | `action_index` out of bounds |
| 409 | action not in `pending_approval`; demo run already in progress; incident already submitted |
| 422 | invalid body (FastAPI validation, e.g. empty `submitted_by`) |
| 503 | `no snapshot yet`: the engine has not read any block yet (the front shows "Waiting for first block") |

CORS open (`*`).

### 2.11 `make` commands (identical for everyone)

The root `Makefile` (T0) contains `include mk/*.mk` and the cross-cutting targets. It does not load `.env`: the Python scripts read it themselves, and a variable given on the command line wins (`NETWORK=local make deploy`). Each task defines its targets in `mk/tN.mk` and never redefines `NETWORK` (it comes from `.env` or the command line).

| Command | What it does | Defined by |
|---|---|---|
| `make setup` | installs Python, npm and Foundry lib dependencies | T0 |
| `make chain` | starts anvil (`--block-time 1`) | T1 |
| `make deploy` | deploys on `$NETWORK`, writes `deployments/$NETWORK.json` and `abi/`; on fuji, requires `FORCE=1` if a deployment already exists (addresses change: tell the team) | T1 |
| `make abi` | exports the ABIs | T1 |
| `make seed` / `make attack SEED=42` / `make normal MINUTES=5` / `make reset` | scenario | T2 |
| `make backend` | `uvicorn backend.main:app --reload --port 8000` | T0 |
| `make frontend` | `npm run dev` in `frontend/` | T6 |
| `make demo` | local chain + deploy + seed + backend with `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false` + frontend | T0 |
| `make verify ID=DEC-…` / `make tamper ID=… FIELD=… VALUE=…` / `make restore ID=…` | verify, tamper for the demo, restore an evidence record | T4 |
| `make eval RUNS=10` | synthetic evaluation on the local chain | T7 |
| `make test` | all suites (calls `test-t0` … `test-t9`) | T0 |
| `make test-tN` | tests of task N | TN |
| `make deploy-aws` | deployment on EC2 | T8 |

### 2.12 Changing the contract

1. Write the request in `docs/contract-requests.md`: what, why, who is impacted.
2. The person holding T0 validates, updates `models.py`, the fixtures (`python -m fixtures._generate`), `types.ts` and this document, in **a single commit** prefixed `contract:`.
3. Everyone rebases. Adding an optional field breaks no one; renaming or removing a field is forbidden without the agreement of all affected tasks.

### 2.13 Available fixtures (`fixtures/`, T0)

| File | Contents | Used by |
|---|---|---|
| `snapshots_attack.jsonl` | 41 `Snapshot`s (one every 2 blocks) of the scenario **without** our reaction | T3 (rule tests), T4 (matrix tests) |
| `snapshots_normal.jsonl` | 41 `Snapshot`s of a normal day (large legitimate deposit, large legitimate borrow, backed rsETH) | T3 (zero alerts ≥ high), T7 |
| `health.json` `state.json` `series.json` `alerts.json` `decisions.json` `verify.json` `incident.json` `dependencies.json` `metrics.json` `demo_run.json` | valid API responses, consistent with the scenario **with** our reaction: R1 alert and decision `DEC-fuji-45201812-1` at block 45,201,812, everything pulled back to the vault ($1,325,000), incident contained. `series.json` is an object keyed by `"<deployment_id>:<asset>"` (the route itself returns an array) | T6 (front), API skeleton |
| `deployments.example.json` `run_record.example.json` | reference formats | T1, T2, T7 |
| `_generate.py` | regenerates everything from `models.py` | T0 |
