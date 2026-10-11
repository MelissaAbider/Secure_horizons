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

## MVP tasks (`TASKS.md`)

One row per task. The check is the task's `make test-tN`, plus its acceptance tests in `TASKS.md`.

| Task | Name | Status | Demo steps covered | Check |
| --- | --- | --- | --- | --- |
| T0 | Repo foundations and shared contract | in progress | all (skeleton) | `make test-t0` |
| T1 | On-chain contracts (local and Fuji) | done (bridge counters CR-003, redeployed on Fuji 2026-10-11, `deployments/fuji.json`) | 1 (simplified vault), 5 | `make test-t1` |
| T2 | Scenario: seed, attack, normal traffic, reset | done (local tests; seed + default attack played on Fuji, see Fuji run) | 5 | `make test-t2` |
| T3 | Monitoring: collector, rules R1–R5 (v3, CR-003/CR-004), state API | done on fixtures, local chain and Fuji live run (R1 critical 3 blocks after the forged release) | 5, 7 | `make test-t3` |
| T4 | Response and evidence | in progress (detection-only: Discord alert from live T3 alerts done; fund withdrawal is phase 2) | 6, 7, 8 | `make test-t4` |
| T5 | Incident and DORA draft | done for detection-only (incident + DORA PDF from live alerts, `/api/incidents/{id}/report.pdf`); Fuji live run pending | 8 | `make test-t5` |
| T6 | Dashboard | in progress (T6 v8 merged; setup page live panel: attack on Fuji, steps with snowtrace links, detections, DORA download, Discord status) | all (screens) | `make test-t6` |
| T7 | Evaluation and metrics | not started | measurement | `make test-t7` |
| T8 | AWS, CI and hosted demo | not started | hosting | `make test-t8` |
| T9 | Jury deliverables | not started | pitch | `make test-t9` |

### Fuji run (2026-10-11, default attack, seed 0, T3 engine live on Alchemy RPC, polling every ~12 s)

| Block | Scenario step | T3 alert |
|---|---|---|
| 59,286,742 | forged release of 5,000 rsETH ([tx](https://testnet.snowtrace.io/tx/0x7450a25e918dac01c7c9cace352f563fb5f7e82895ee1fb02b2e86eb8d33f8dd)) | — |
| 59,286,745 | | `R1_BRIDGE_INVARIANT` critical, exposure $1,325,000 |
| 59,286,754 | 5,000 rsETH posted as collateral on lend-eth ([tx](https://testnet.snowtrace.io/tx/0xa0ada7b31b4d824c1ac9a72994a71a227c656e77d05d26743b6426bd9b71570f)) | `R2_COLLATERAL_SURGE` critical at 59,286,755 |
| 59,286,759 | first borrow of 100 WETH ([tx](https://testnet.snowtrace.io/tx/0x58fd7289c7a9fff89430e9e041276fbef847b3e887106ff892ea103dcdf98b17)) | `R3_LIQUIDITY_DRAIN` high at 59,286,762, critical at 59,286,778 |
| 59,286,788 | lend-eth WETH drained (600 WETH borrowed, lender stuck) | `R4_EXITABILITY_DROP` high at 59,286,787, critical at 59,286,792 |
| 59,286,825 | protocol guardian freezes rsETH ([tx](https://testnet.snowtrace.io/tx/0xf9a64c784fea8d92c13f5013a78199c62464492316c2a97339eb991c35e02980)) | `R5_CONTAINMENT` critical at 59,286,829 |

No response was executed in this run (T4 not wired yet): the vault positions stayed in place, so this measures detection only.

## Session log

Newest first. One line. No narrative.

| Date | Who | Did | Left at |
| --- | --- | --- | --- |
| 2026-10-11 | T3 | Three live layers wired: R1-R5 sync rules, R6 local Elliptic Snapshot monitor, R7 Claude Haiku 4.5 via Bedrock; R7 is asynchronous with one bounded in-flight request and exact-block late consensus/persistence | Real Bedrock invocation verified in us-west-2. R6/R7 thresholds are development policy, not frozen evaluation metrics. Check: `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.pytest_cache/t3-live-layers`. Not committed. |
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
