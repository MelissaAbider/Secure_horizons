# Contract: backend side

> Light version of `TASKS.md` (full detail there). Same numbering, so a reference like "2.7" means the same thing in both.

### 2.5 Data conventions

- **Token amounts**: strings in base units (`"150000000000000000000"` = 150 WETH). Never a float for an on-chain amount.
- **Dollar values**: float, for display and exposure.
- **Rates and ratios**: integers in basis points (1% = 100 bps).
- **Time**: UTC datetime with timezone, serialized ISO 8601 (`2026-10-11T08:00:26Z`). Always keep the block number too.
- **Assets**: by symbol (`USDC`, `WETH`, `rsETH`). **Deployments**: by id (`lend-eth`, `lend-avax`).
- **JSON keys**: snake_case. All model keys are always present, `null` when empty (never `exclude_none`).
- **Identifiers**:
  - alert: `ALT-<network>-<block>-<rule_id>-<deployment_id ou global>-<asset ou all>`
  - decision: `DEC-<network>-<block>-<n>` (n = 1, 2… within the same block)
  - incident: `INC-<yyyymmdd>-<nnn>`
  - scenario run: `RUN-<yyyymmddHHMMSS>-<kind>-<seed>`

### 2.6 Data models (`backend/models.py`, T0, source of truth)

Summary of the objects exchanged between tasks. The Python file is authoritative; the front's TypeScript types (`frontend/src/types.ts`) are its exact mirror.

| Object | Produced by | Read by | Main fields |
|---|---|---|---|
| `Snapshot` | T3 (collector); T7 (replay, phase 2) | T3, T4, T5, T7 | `network, chain_id, block_number, block_time, source, reserves[], tokens[], positions[], vault` |
| `ReserveSnapshot` | T3 | T3, T4, T6 | `deployment_id, asset, asset_address, decimals, total_supplied, total_borrowed, available_liquidity, total_collateral, utilization_bps, supply_apy_bps, borrow_apy_bps, ltv_bps, borrowable, frozen, paused, price_usd` |
| `TokenSnapshot` | T3 | T3, T6 | `symbol, address, decimals, total_supply, backing, backing_ratio_bps, price_usd` (backing only for rsETH) |
| `PositionSnapshot` | T3 | T3, T4, T5, T6 | `wallet, deployment_id, asset, supplied, withdrawable_now, withdrawable_ratio_bps, value_usd, withdrawable_usd` |
| `VaultStatus` | T3 | T4, T6 | `address, deposits_paused, idle_balances{symbol: base units}` |
| `Alert` | T3 | T4, T5, T6, T7 | `id, rule_id, severity, network, deployment_id, asset, block_number, block_time, detected_at, title, explanation, metrics{}, exposure_usd, rules_version` |
| `Action` | T4 | T4, T5, T6 | `type, mode, status, params{}, tx_hash, amount, executed_at, note` |
| `Decision` | T4 | T5, T6, T7 | `id, created_at, network, block_number, alert_ids[], severity, exposure_usd, withdrawable_usd, exit_cost_bps, matrix_cell, rationale, actions[], inputs_hash, rules_version, playbook_version, record_hash, anchor_tx, anchor_block` |
| `VerifyResult` | T4 | T6 | `decision_id, match, stored_hash, recomputed_hash, anchored, anchor_tx, anchor_block, diffs[]` |
| `Incident` | T5 | T6, T9 | `id, title, status, severity, opened_at, detected_at, contained_at, alert_ids[], decision_ids[], exposure_usd, saved_usd, at_risk_usd, dora, timeline[]` |
| `DoraAssessment` | T5 | T6 | `criteria, thresholds_met[], is_major, legal_basis, aware_at, classified_at, deadlines, report_markdown, ai_drafted_sections[], submitted, submitted_by, submitted_at` |
| `Dependency` | T5 | T6 | `id, name, kind, provider, criticality, supports[], fallback, status` |
| `StateResponse`, `SeriesPoint`, `Health` | T3 | T6 | see 2.9 |
| `DemoRun`, `RunRecord` | T2 | T6, T7 | see T2 |
| `EvalMetrics` | T7 | T6, T9 | see T7 |

Definitions to follow:

- `StateResponse.totals`: `idle_usd` = Σ vault balances × price; `withdrawable_usd` = Σ `withdrawable_usd` of positions; `value_usd` = Σ `value_usd` of positions + `idle_usd`; `at_risk_usd` = Σ (`value_usd` − `withdrawable_usd`) of positions.
- `StateResponse.risk_level`: maximum severity of the conditions **still true** in the latest snapshot (an alert whose condition has disappeared no longer counts); `info` otherwise.
- `EvalMetrics.synthetic`: `*_rate` are fractions from 0 to 1; `*_pct_*` are percentages from 0 to 100; `ttd_blocks_p50` and `ttd_blocks_p90` are `-1` if no attack is detected.
- `DoraCriteria` also contains three optional fields from Art. 9(1): `counterparts_affected_pct` (default 0), `transactions_affected_count_pct` (default 0), `relevant_clients_affected` (default false).

Allowed values: `severity ∈ {info, warning, high, critical}`; `Action.type ∈ {NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW, FULL_EXIT, UNPAUSE_DEPOSITS, OPEN_INCIDENT}`; `Action.mode ∈ {auto, human}`; `Action.status ∈ {planned, executed, failed, skipped, pending_approval, approved, rejected}`.

### 2.7 MVP detection rules (deliberately simple)

Five rules, each on **a single indicator**. Thresholds in `backend/config/rules.yaml` (T3). We will make them more complex in phase 2.

| Id | Indicator | Scope | Condition | Severity |
|---|---|---|---|---|
| `R1_BACKING_DROP` | backing of a bridged token: `backing_ratio_bps` | global, per token (rsETH) | `< 9900` | critical |
| `R2_LIQUIDITY_DROP` | drop in a market's available liquidity, relative to its maximum over the last `window_blocks` snapshots | each borrowable reserve where the vault has a position | drop ≥ 30% → high; ≥ 60% → critical | high / critical |
| `R3_UTILIZATION_HIGH` | `utilization_bps` | each borrowable reserve where the vault has a position | ≥ 9000 → warning; ≥ 9800 → critical | warning / critical |
| `R4_POSITION_STUCK` | withdrawable share of our position: `withdrawable_ratio_bps` | each vault position | < 8000 → high; < 5000 → critical | high / critical |
| `R5_RESERVE_FROZEN` | `frozen` or `paused` goes from false to true | each reserve of a deployment where the vault has at least one position | state change | high |

Common details:

- **Exposure** (`exposure_usd`):
  - R1: value of **all** vault positions in the deployments that accept this token as collateral (`ltv_bps > 0` for this token in this deployment);
  - R2, R3, R4: value of the vault position in the reserve concerned;
  - R5: value of all vault positions in this deployment.
- **No duplicates**: an alert `(rule_id, deployment_id, asset)` is emitted only once per severity. It is re-emitted only if the severity rises, or if the condition disappears and then comes back.
- **Explanation**: one sentence in English, with the numbers, e.g. `rsETH backing fell to 19.4 % (1,200 WETH backing for 6,200 rsETH supply).`
- `rules_version` = `"sha256:" + sha256(exact contents of rules.yaml)`.
- Default `window_blocks`: 20.

Initial `backend/config/rules.yaml`:

```yaml
version: 1
window_blocks: 20
R1_BACKING_DROP:     { enabled: true, min_backing_ratio_bps: 9900 }
R2_LIQUIDITY_DROP:   { enabled: true, high_drop_pct: 30, critical_drop_pct: 60 }
R3_UTILIZATION_HIGH: { enabled: true, warning_bps: 9000, critical_bps: 9800 }
R4_POSITION_STUCK:   { enabled: true, high_below_bps: 8000, critical_below_bps: 5000 }
R5_RESERVE_FROZEN:   { enabled: true }
```

### 2.8 MVP response matrix (`backend/config/playbook.yaml`, T4)

| Alert severity | Exposure | Actions (in this order) |
|---|---|---|
| critical | ≥ $1,000 | `NOTIFY` (auto) → `PAUSE_DEPOSITS` (auto, if not already paused) → `EMERGENCY_WITHDRAW` (auto) for **each affected position** with `withdrawable_now > 0` → `OPEN_INCIDENT` (auto) → `UNPAUSE_DEPOSITS` (human, `pending_approval`) |
| high | ≥ $1,000 | `NOTIFY` (auto) → `PAUSE_DEPOSITS` (auto) → `EMERGENCY_WITHDRAW` (human, `pending_approval`) for each affected position → `OPEN_INCIDENT` (auto) |
| warning | any | `NOTIFY` (auto) |
| info, or exposure < $1,000 | — | `NOTIFY` (auto) if severity ≥ high, otherwise nothing |

"Affected positions": for R1, all vault positions in the deployments that accept the token as collateral; for R2 to R4, the reserve's position; for R5, all positions of the deployment.
A decision groups all new alerts of the same snapshot. `exit_cost_bps` = 0 in the MVP (a withdrawal from a lending protocol only costs gas). `matrix_cell` = `"<severity>|exposure>=1k|exit_possible"` or `"…|no_liquidity"`.

### 2.10 Store and internal wiring (summary)

- `backend/store.py`: one shared instance `store` with `add_snapshot`, `latest_snapshot`, `snapshots(limit)`, `add_alerts`, `alerts(since_block)`, `add_decision`, `update_decision`, `decisions`, `get_decision`, `upsert_incident`, `incidents`, `get_incident`, `reset()` (empties everything, increments `generation`).
- `Engine(store)` (T3): `on_alerts(handler)`, `process(snapshot) -> list[Alert]`, `async run_forever()`.
- `Responder(store, executor)` (T4): `handle(alerts, snapshot) -> list[Decision]`, `on_decisions(handler)`; pure `plan_actions(alerts, snapshot, playbook) -> list[Action]` (reused by verify).
- `IncidentManager(store)` (T5): `handle(decisions, alerts, snapshot) -> Incident | None`.
- `get_executor()` (T4): singleton, dry-run when `DRY_RUN_ACTIONS=true`.

Wiring (in `backend/main.py`, T0): `responder = Responder(store, get_executor())`, `engine.on_alerts(responder.handle)` then `responder.on_decisions(incidents.handle)`. `main.py` only mounts and wires the modules that exist: as soon as a task adds its file (for example `backend/responder.py`), it is used with no edit to `main.py`, so no file ever has two authors. A missing module is skipped (its routes answer 404 until then; the dashboard has its own fixture mode meanwhile). A module that exists but fails to import raises.

Shared operating rules:

- **Subscribers outside the loop**: the engine calls subscribers with `await asyncio.to_thread(handler, alerts, snapshot)`, one call at a time, in snapshot order. A slow response (Fuji transactions) therefore blocks neither the API nor the dashboard.
- **Maintenance mode**: as long as the file `data/runtime/<network>/maintenance.flag` exists, the engine keeps reading and storing snapshots but **evaluates no rule**. When the file disappears, or when `store.generation` changes, it empties its window. T2 creates this file at the start of `seed` and `reset` and deletes it at the end (in a `finally`). Without it, setting up the liquidity would look like an attack.
