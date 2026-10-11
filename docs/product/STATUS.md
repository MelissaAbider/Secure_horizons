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
| 1 | Connect test Safe on Fuji | done (T10: real Safe 1.4.1, 2 of 3 owners; the incident scenario still uses TreasuryVault) | `make seal-show NETWORK=fuji` |
| 2 | Aave + Benqi list, sealed | done (T10, with the simulated markets lend-avax and lend-eth) | `make seal-show NETWORK=fuji` |
| 3 | Rules separated from instructions | not started |  |
| 4 | Normal move accepted inside list and caps | in progress (T10: the list is enforced on-chain; caps not built yet) | `make seal-demo` |
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
| T4 | Response and evidence | in progress | 6, 7, 8 | `make test-t4` |
| T5 | Incident and DORA draft | not started | 8 | `make test-t5` |
| T6 | Dashboard | not started | all (screens) | `make test-t6` |
| T7 | Evaluation and metrics | not started | measurement | `make test-t7` |
| T8 | AWS, CI and hosted demo | not started | hosting | `make test-t8` |
| T9 | Jury deliverables | not started | pitch | `make test-t9` |
| T10 | Sealed list: Safe, teller-window module, Merkle root (`docs/tasks/T10.md`) | done v1 (12 Foundry + 8 pytest on anvil; Fuji run below); caps and the facts gate not built | 1, 2, 4 (list only) | `make test-t10` |

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

### T10 Fuji run (2026-10-11, `make seal-demo`, 48 s)

Safe [`0x193b…2177`](https://testnet.snowtrace.io/address/0x193b75985E4Fe8E54c43B637E1d7748d5E1F2177) (canonical SafeL2 1.4.1, 2 of 3 owners), module [`0xA1F1…00Bd`](https://testnet.snowtrace.io/address/0xA1F109f7861b69BFEeaDf91Be75a14aD533B00Bd) enabled by 2 owner signatures ([tx](https://testnet.snowtrace.io/tx/0x3943dd46a304e779f40929831aefeea86d6ff8201441b6331ddbb1daf801ec6f)). Addresses and the published list: `sealed/deployments/fuji.json`.

| Step | Result |
|---|---|
| Owners seal lend-avax (3 operations) | root signed by 2 of 3 owners ([tx](https://testnet.snowtrace.io/tx/0x6fd0e3a5278332a11f51ef52508c990e90c2115e5e832dd4f7af64ba34e8f62f)) |
| Agent: deposit 100,000 USDC on lend-avax | executed by the module ([approve](https://testnet.snowtrace.io/tx/0xf4d71bc6848181962c96740acff8bc1bb0d47af6a44ad9edf4ff60ac5e0c5e2e), [supply](https://testnet.snowtrace.io/tx/0xbcc37272933c8ef7b753ec93a2c0728ed285f68ec9a60d2384b8958aea7f0d1d)) |
| Agent: transfer 500,000 USDC to 0x9c…f1 | refused by the platform; forced through the module: `NotInSealedList`, reverted ([tx](https://testnet.snowtrace.io/tx/0x03c309a8cec1c2dec4babcfe2ed48beebcf58727c18be89c2adda28d45fbfc02)) |
| Agent: withdraw 60,000 USDC to 0x9c…f1 | refused; forced: reverted ([tx](https://testnet.snowtrace.io/tx/0xf06d661449f6881c6acfdafc840d417362f21b3bb5a2dfc20a498ed954e46778)) |
| Agent: deposit on an "audited 25%" protocol / on unticked lend-eth | refused; forced: reverted ([tx](https://testnet.snowtrace.io/tx/0xbb3cedfdc0dab030425e65922f3eb4ce845be8dd7916ac925ec95907670bbf34), [tx](https://testnet.snowtrace.io/tx/0x954c5f3a37374044e5e1ea13b75d35d00f0498caf460f79e17d24c68d4082c32)) |
| Owners tick lend-eth: new root, 2 signatures | [tx](https://testnet.snowtrace.io/tx/0x022a36983835ca29bdeeb523e120b02903e1485af3a2c61beb49c793eba091da); the lend-eth deposit then runs ([supply](https://testnet.snowtrace.io/tx/0xb842dbaccb187ed86f89a850ae682ee77a07cf83b4c0eb539db3dc5b4aa9ade5)) |
| Exit | everything withdrawn back to the Safe, so lend-avax and lend-eth reserves end as they started |

One earlier Fuji run stalled for about 16 minutes between two steps (an RPC call that did not return); the rerun had no stall. Keep `NETWORK=local make seal-demo` as the fallback for a live demo.

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
