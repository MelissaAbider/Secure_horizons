# Status

Single source of truth for where we are. If this file disagrees with a chat, this file wins.

Rules:

- English only.
- One current task. Do not start a second without parking the first as `blocked` or `done`.
- Update this file at the end of every coding session, in the same change as the work.
- Do not mark a demo step `done` unless the check column command was actually run.
- Do not invent progress. `not started` is a valid state.

## Now

- Phase: T3 surveillance
- Current task: T3 version-3 hardening implemented; 67 T3 and 22 T0 regression tests pass. T3 as a whole is NOT complete.
- Blocker: canonical cross-chain message evidence is absent from the shared data contract; bridge counters cannot prove real forgery. Live collector and state API are not implemented here; contract acceptance is pending in CR-004.
- Next: agree the independent source-evidence interface, implement the T3 read-only collector and live coverage-aware state API, then verify on deployed contracts and held-out data. Do not claim real-incident accuracy from synthetic fixtures.

## T3 verification and handoff

- Command: `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.pytest_cache/t3-pre-push` — 89 passed, one existing Starlette/httpx deprecation warning.
- Synthetic attack snapshots: 8 alerts including global bridge pause; normal snapshots: 0 alerts. Counts validate these fixtures only.
- Coverage: exact threshold arithmetic, legitimate uncorroborated inflows, rolling/slow liquidity drains, active freezes/bridge pauses at startup, unknown evidence, stale/future timestamps, invalid/partial snapshots, retry after persistence error, serialized nonblocking handlers, maintenance, mocked RPC failover and lagging RPC rejection.
- Real cross-chain proof, source finality, full reorg handling, representative false-positive rates, response execution and live-chain latency remain unverified. No claim of zero misses or guaranteed fund recovery.
- Scope: T3 rules/config/engine/tests and tracking/specification only. Shared models, existing fixtures and other tasks' implementation are unchanged by this hardening.
- Git delivery target: `origin/feature/t3-kelpdao-surveillance` only, as requested by Melissa. Pre-push verification passed; report progress before publication. Never push this work directly to `main` or `master`.

## Demo path

| Step | Name | Status | Check |
| --- | --- | --- | --- |
| 1 | Connect test Safe on Fuji | not started |  |
| 2 | Aave + Benqi list, sealed | not started |  |
| 3 | Rules separated from instructions | not started |  |
| 4 | Normal move accepted inside list and caps | not started |  |
| 5 | April 2026 incident replay | not started |  |
| 6 | Circuit breaker freezes and pulls back | not started |  |
| 7 | 14% bait blocked after on-chain reread | not started |  |
| 8 | Signed replayable proof, DORA draft not sent | not started |  |

Allowed status values: `not started`, `in progress`, `blocked`, `done`.

## Session log

Newest first. One line. No narrative.

| Date | Who | Did | Left at |
| --- | --- | --- | --- |
| 2026-10-10 | T3 | Hardened evidence handling, exact thresholds, persistent containment, input checks and engine dispatch; 89 tests pass | Local only; live proof/collector/API and CR-004 integration remain pending. |
| 2026-10-10 | T3 | Implemented R1–R5, replay engine, regenerated fixtures, and tests | 27 T0+T3 tests pass; live collector waits for T1/T2. |
| 2026-10-10 | T3 | Replaced generic surveillance rules with KelpDAO bridge-to-Aave causal rules in TASKS | Implementation waiting for T0 fixtures and T1 bridge counters. |
| 2026-10-10 | setup | Moved skills to `.agents/skills` and removed `.devin` | No application code. Stack undecided. |
| 2026-10-10 | setup | Loosened agent loop: build by default, hard-stop only on security | No application code. Stack undecided. |
| 2026-10-10 | setup | Added orient and verify-step skills; one-task loop in AGENTS.md | No application code. Stack undecided. |
| 2026-10-10 | setup | Added English agent context, skills, and this tracker | No application code. Stack undecided. |
