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
- Current task: T3 MVP implementation complete and rules reviewed against the KelpDAO timeline (version 4: live bridge mismatch critical when exposed, sticky R1, window-wide correlation for R2, early drain threshold for R3). 117 T3 tests pass; deployed-chain smoke test is opt-in and has not run here.
- Validation limit: no deployed-node acceptance result in this environment. Independent forensic proof of the historical cross-chain message is outside this MVP completion and is not inferred from bridge counters.
- Next: review the local T3 changes; when a deployed endpoint is available, run the read-only `T3_LIVE=1` check. No other task's implementation is part of this work and no automatic push is authorized.

## T3 verification and handoff

- T3 command: `python -m pytest backend/tests/test_t3_rules.py backend/tests/test_t3_hardening.py backend/tests/test_t3_engine.py backend/tests/test_t3_collector.py backend/tests/test_t3_api.py -q -p no:cacheprovider --basetemp=.pytest_cache/t3-complete` — 109 passed, 1 opt-in live test skipped; existing Starlette/httpx and websockets deprecation warnings.
- Regression command: `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.pytest_cache/t3-review-full` — 139 passed (117 T3 + 22 existing T0), 1 live test skipped; no changes to T0 implementation or tests.
- Collector and CLI: `python -m backend.collector --once [--block N]`; continuous monitoring: `python -m backend.engine --loop`; replay: `python -m backend.engine --replay fixtures/snapshots_attack.jsonl`. CLI help and mocked JSON collection tested.
- Make targets `monitor-once` (optional `BLOCK=N`) and `monitor` added alongside `test-t3` and `replay-t3`. GNU make is not installed here; Python equivalents were verified.
- Deployed read-only smoke: set `NETWORK=local`, `T3_LIVE=1`, a configured RPC and seeded deployment, then run `python -m pytest backend/tests/test_t3_collector.py -q`. This test sends no transactions.
- Synthetic attack snapshots: 8 alerts including global bridge pause; normal snapshots: 0 alerts. Counts validate these fixtures only.
- Coverage: exact threshold arithmetic, legitimate uncorroborated inflows, rolling/slow liquidity drains, active freezes/bridge pauses at startup, unknown evidence, stale/future timestamps, invalid/partial snapshots, retry after persistence error, serialized nonblocking handlers, maintenance, mocked RPC failover and lagging RPC rejection.
- Real cross-chain proof, source finality, full reorg handling, representative false-positive rates, response execution and live-chain latency remain unverified. No claim of zero misses or guaranteed fund recovery.
- Scope: only T3-owned implementation and tests plus tracking. Shared models, fixtures, chain/store helpers, application wiring and all other tasks' code are unchanged. The existing application automatically loads the new T3 router.
- Delivery checklist: read-only collector complete; same-block reads and in-flight block-hash check complete; R1–R5 and latch complete; monitor loop complete; four API routes complete; command targets complete; mocked full-path tests complete; deployed smoke test not run.
- API schemas remain unchanged. `X-Monitoring-Status` and `X-Monitoring-Issues` headers expose missing/stale coverage; `/health` becomes degraded and `/state` does not imply safety when evidence is unavailable.
- Current delivery is local and uncommitted; no push in this completion session.
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
| 2026-10-11 | T3 | ML round 3: 34 v2 features (multi-scale, surge memory, concentration) + search over 240 one-class configs selected on normal-only cost; Elliptic Envelope on v2 flows wins: KelpDAO recall 0.76, precision 0.86, 0 pre-attack FP, +29 blocks, 0.87% held-out FP | Ceiling (not selectable, uses attack): OC-SVM recall 0.99 but 28% FP on normal days. Not wired into T3, not committed. |
| 2026-10-11 | T3 | ML round 2: scenario features per asset/phase on real Aave events; LOF fitted on normal only detects KelpDAO at +29 blocks, recall 0.59, precision 0.80, 0 pre-attack FP, 1.8 FP per normal file | Cross-incident supervised models rejected (round 1: ROC 0.54–0.80, no transfer). Results in data/external/ml/kelpdao/results.md. Not wired into T3, not committed. |
| 2026-10-11 | T3 | Cleaned ML data: train 3,406 windows / 328 pos over 7 incidents, test = KelpDAO 1,683 / 80 pos, 5 LOIO folds, integrity report | Round-1 benchmark: 6 models, none usable (report in data/external/ml/results/report.md). |
| 2026-10-11 | T3 | Collected real incident data for ML: 15 incidents via SQD (no key), XChainWatcher 2.2 GB, DeFiHackLabs index; built 11,675 labeled windows (597 positive, 12 incidents) | Dataset frozen in data/external (gitignored); scripts in evaluation/data_sources. Not committed. |
| 2026-10-10 | T3 | KelpDAO deep review: R1 critical+sticky when exposed, R2 window correlation, R3 post-anomaly drain threshold; 139 tests pass | Local, uncommitted; rules version 4 documented in THRESHOLDS.md. |
| 2026-10-10 | T3 | Completed collector, four state routes, monitor targets and mocked full-path coverage; 109 T3 tests pass | Local, uncommitted; deployed smoke opt-in and not run. No other task changed. |
| 2026-10-10 | T3 | Hardened evidence handling, exact thresholds, persistent containment, input checks and engine dispatch; 89 tests pass | Local only; live proof/collector/API and CR-004 integration remain pending. |
| 2026-10-10 | T3 | Implemented R1–R5, replay engine, regenerated fixtures, and tests | 27 T0+T3 tests pass; live collector waits for T1/T2. |
| 2026-10-10 | T3 | Replaced generic surveillance rules with KelpDAO bridge-to-Aave causal rules in TASKS | Implementation waiting for T0 fixtures and T1 bridge counters. |
| 2026-10-10 | setup | Moved skills to `.agents/skills` and removed `.devin` | No application code. Stack undecided. |
| 2026-10-10 | setup | Loosened agent loop: build by default, hard-stop only on security | No application code. Stack undecided. |
| 2026-10-10 | setup | Added orient and verify-step skills; one-task loop in AGENTS.md | No application code. Stack undecided. |
| 2026-10-10 | setup | Added English agent context, skills, and this tracker | No application code. Stack undecided. |
