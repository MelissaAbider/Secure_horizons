# "DeFi treasury monitoring" MVP: task plan

> Team reference document. Each task (T0 to T9) is run **on its own, with its own Claude Code**.
> 1. First read **"Tasks at a glance"** right below: one short, concrete card per task, so you can pick yours.
> 2. Then give your Claude Code section 1 (context), section 2 (interface contract) and **your detailed sheet** from section 3.
> 3. Section 2 is **frozen**: nobody changes it alone (see 2.12).

---

## Tasks at a glance

Ten tasks, each run by one person with their own Claude Code. This part says **concretely** what each task builds, what must work at the end and how we know it is done. The rest of the document (interface contract, detailed sheets) is mainly meant for the Claude Code instances.

**Order:** T0 first (everyone starts from that commit), then everything else in parallel on mocks. T2 only waits for the T1 contracts to deploy locally.

**Link with `docs/product/`.** `docs/product/STATUS.md` keeps tracking progress, task by task. This plan covers demo steps 1 (with a simplified vault instead of a Safe), 5, 6, 7 (the bait deposit is refused because deposits are paused and every fact is re-read on-chain) and 8. Steps 2 to 4 (sealed list, rules versus instructions, the agent's normal move) are phase 2: see section 5 and `docs/product/DECISIONS.md`.

| Task | What it delivers | Needs (mock meanwhile) | Unblocks |
|---|---|---|---|
| **T0** Foundations | repo skeleton, models, helpers, store, API entry point, fixtures, Makefile, guardrails | nothing | everyone |
| **T1** On-chain contracts | tokens, rsETH bridge with its flaw, oracle, 2 lending protocols, vault with guardian, evidence registry; local and Fuji deployment; ABIs; funding the roles with test AVAX | T0 | T2, T3, T4, T7, T8, T9 |
| **T2** Scenario | seed, attack (3 variants, random seed), normal traffic, reset, run ground truth, demo routes | T1 (local chain as soon as `make deploy` works) | T3, T4, T5, T6, T7 |
| **T3** Monitoring | collector, rules R1 to R5, engine, state routes | T1/T2 (series `fixtures/snapshots_*.jsonl`) | T4, T5, T6, T7 |
| **T4** Response and evidence | matrix, on-chain execution, notifications, anchored evidence, `verify`, approvals | T3 (hand-built alerts), T1 (dry-run) | T5, T6, T7, T9 |
| **T5** Incident and DORA | incidents, timeline, DORA classification, report, dependency register | T4 (hand-built decisions) | T6, T9 |
| **T6** Dashboard | all views, controllable demo | T3, T4, T5, T2, T7 (fixtures, then T0 skeleton) | T9 (screenshots, video) |
| **T7** Evaluation | simple metrics on synthetic runs, report | T2, T3, T4 (local chain) | T6, T9 |
| **T8** AWS and CI | images, compose, EC2, SNS, S3, Bedrock, CI, fallback plan | T0 (then everything else for going live) | E2E-3, T9 |
| **T9** Deliverables | README, playbook, compliance, defense sheet, deck, video, pitch | everything (provisional numbers marked meanwhile) | the submission |

---

### T0 · Foundations: the repo skeleton everyone clones

**In one sentence.** The first commit merged into `main`: a repo where every API route already answers with sample data (the "fixtures"), so each task can start alone without waiting for anyone.

**Suggested profile.** Python (FastAPI, Pydantic) with a bit of TypeScript and Makefile. No blockchain knowledge needed: the helpers follow the spec in section 2.

**Concretely, you build:**
- the **data contract in code**: `backend/models.py` (Pydantic models from 2.6) and its exact mirror `frontend/src/types.ts`;
- the **shared building blocks**: `settings.py` (`.env` variables, test keys derived from anvil's public mnemonic, the local chain), `chain.py` (read and send transactions), `store.py` (memory + JSONL files);
- the **API entry point** `backend/main.py`: mounts the router of each task and wires engine → responder → incidents, for the modules that exist. A task plugs in by adding its own file, so T0 never creates a file another task owns;
- the **fixtures** that tell the attack story, regenerable with `python -m fixtures._generate`;
- the **tooling**: `Makefile`, `.env.example`, `.gitignore`, gitleaks (secret detector) as pre-commit, `CLAUDE.md`, `docs/contract-requests.md`.

**At the end, we must be able to:**
1. run `make backend` then `curl -s localhost:8000/api/state` and get the `state.json` fixture; `localhost:8000/docs` lists every route in 2.9;
2. run `make test-t0` and see everything green;
3. run `make help` and see at least `setup backend demo test test-t0`;
4. read the attack story in the fixtures: critical `R1_BACKING_DROP` alert at block 45,201,812, exposure $1,325,000, decision `DEC-fuji-45201812-1`, 250 WETH + 700,000 USDC pulled back to the vault, `at_risk_usd = 0`, incident `INC-20261011-001`, `verify` = MATCH.

**Key specs.**
- Decision `DEC-fuji-45201812-1`: exactly 8 actions in this order, `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW` (lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH), `OPEN_INCIDENT`, `UNPAUSE_DEPOSITS` (pending human approval).
- `snapshots_attack.jsonl` and `snapshots_normal.jsonl`: 41 lines each, every line valid as a `Snapshot`.
- Thread-safe store, at most 2,000 snapshots in memory; `reset()` clears everything and increments `generation`.
- `send()`: per-sender lock, estimated gas × 1.3, 120 s timeout, compatible with web3.py 6 and 7.
- `get_executor()` always returns the same instance; dry-run (simulation with no real transaction) if `DRY_RUN_ACTIONS=true`.
- A single uvicorn worker; engine started only if `ENGINE_ENABLED=true`. No make target sets `NETWORK`.
- No business logic in T0 files; no key in any versioned file.

**Deliverables.** `backend/models.py`, `settings.py`, `chain.py`, `store.py`, `fixtures.py`, `main.py`, `fixtures/*`, `frontend/src/types.ts`, `Makefile`, `mk/t0.mk`, `CLAUDE.md`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `requirements.txt`, tests `backend/tests/test_t0_*.py`. Branch `t0-foundations`, merged into `main` before everything else.

**Acceptance tests (the ones that matter).**
- T0-01 / T0-02: each fixture validates against its model and tells the story (`incident.saved_usd == 1325000.0`, `state.positions == []`, `verify.stored_hash` = `record_hash` of the R1 decision).
- T0-03: recomputing keccak256 (a cryptographic hash) of the canonical JSON of the R1 decision gives back `record_hash`.
- T0-05: in `local` with no key, `deployer` = `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`, 3 bots; in `fuji` with no key, `private_key("guardian")` raises `RuntimeError`.
- T0-04: `main.py` imports and mounts the router of every task module that exists.
- T0-10 / T0-11: gitleaks finds no secret; `types.ts` compiles with `--strict`.

**While waiting for the others.** Nothing to wait for: T0 depends on nobody, its only input is section 2 of this document. Afterwards, T0 approves contract change requests (2.12) and coordinates integration.

**Details for Claude Code.** Detailed sheet T0, section 3 of this document.

---

### T1 · Contracts: the scenario's on-chain mini-world

**In one sentence.** Write, test and deploy (local anvil chain, then Avalanche Fuji testnet) the 7 Solidity contracts (programs stored on the blockchain) that reproduce the Kelp/Aave scenario: tokens, rsETH bridge, price oracle, two lending protocols, the vault and the evidence registry.

**Suggested profile.** Solidity + Foundry (`forge`, `anvil`), a bit of Python and bash for the scripts.

**Concretely, you build:**
- the **tokens** `MockERC20` (USDC 6 decimals, WETH 18) and `RsETH`, plus `MockBridge` which mints rsETH, whose `forgedRelease` mints **with no backing and no access control** (that is the flaw), and `MockOracle` (dollar prices × 1e8);
- `MiniLend`, a simplified lending protocol (supply, collateral, borrow, withdraw, freeze, pause, rate model), deployed twice: `lend-eth` and `lend-avax`;
- `TreasuryVault`, the vault: the guardian (our response bot) can pause deposits and call `emergencyWithdraw`, which always sends funds back to the vault; `EvidenceRegistry` stores the hashes (`anchor`);
- `script/Deploy.s.sol` + helper scripts: writes `deployments/<network>.json`, exports the ABIs (the description of the functions the backend uses to call the contracts), funds the Fuji roles.

**At the end, we must be able to:**
1. `make chain` then `make deploy` on a fresh anvil → valid `deployments/local.json`, with the 9 addresses identical to those in the fixtures (USDC `0x5FbD…0aa3`, …, EvidenceRegistry `0x2279…eBe6`);
2. read on each `MiniLend`: USDC price `1e8`, WETH and rsETH `2500e8`; `getAssets()` = `[USDC, WETH, rsETH]`; LTV (borrowable share of collateral) 8000 / 8000 / 7500; no token minted by T1;
3. replay the attack: `forgedRelease` of 5000 rsETH drops `backingRatioBps` to `1935`; a guardian that exits before the drain recovers `150e18` WETH and `400_000e6` USDC (100%), a passive supplier recovers `0` afterwards;
4. `make test-t1` green; on Fuji, `deployments/fuji.json` + `fuji.md` committed, the 8 roles hold ≥ 0.5 AVAX, and `make deploy` is refused without `FORCE=1`.

**Key specs.**
- Exact signatures, events and **revert messages** from section 2.2 (e.g. `"MiniLend: frozen"`, `"Vault: only guardian or owner"`); `ReserveData` field order to the letter.
- `liquidity = totalSupplied - totalBorrowed` (accounting); collateral is a separate balance, never borrowable; liquidity check **before** health check.
- Withdraw allowed if reserve is `frozen`, everything blocked if `paused`; `withdraw(max)` = `min(position, liquidity)`, `0` without revert if nothing to withdraw.
- Rates (u in bps → supply/borrow): 6000 → 165/325; 5500 → 143/306; 10000 → 6715/7900.
- Mandatory deployment order (nonces 0 to 8), prices set **after** the 9 deployments; file written as `.pending.json`, promoted after verifying on-chain code; no key in the repo or the logs.

**Deliverables.** `contracts/**` (`src/` 7 contracts, `script/`, `test/`), `abi/<Contrat>.json` ×7 committed, `deployments/local.json`, `fuji.json`, `fuji.md`, `history/`, `mk/t1.mk` (`chain`, `deploy`, `abi`, `fund-roles`, `test-t1`, `t1-*`), `backend/tests/test_t1_deployment.py`.

**Acceptance tests (the ones that matter).**
- T1-06: deposit 1200 + forged mint 5000 → supply `6200e18`, ratio `1935`.
- T1-26: the seed from 2.2 passes **without touching prices**; `lend-eth` WETH at 6000 bps (165/325), `lend-avax` at 5500 (143/306); remaining margin exactly 195 WETH.
- T1-27: drain with no reaction → liquidity 0, `6715`/`7900`, next tranche `"MiniLend: insufficient liquidity"`, `emergencyWithdraw` returns `0`.
- T1-28: guardian exits before the drain → `150e18` and `400_000e6` recovered, passive bot → `0`.
- T1-37: the 9 deployment addresses = those in the fixtures.
- T1-38 to T1-41: `local.json` in the right format, code present at the addresses, 7 ABIs, correct on-chain config and roles.

**While waiting for the others.** T1 waits for nobody: everything runs on **local anvil** with the public accounts (mnemonic `test test … junk`), no key to write; before the T0 skeleton, run `NETWORK=local make -f mk/t1.mk <cible>`. Ship the 7 ABIs and a local `make deploy` fast to unblock T2, T3, T4; Fuji afterwards, as soon as the `DEPLOYER_PK` key is funded.

**Details for Claude Code.** Detailed sheet T1, section 3 of this document.

---

### T2 · Scenario: prepare the chain, play the attack, reset

**In one sentence.** The scripts that put the test chain in its starting state, replay the Kelp/Aave attack reproducibly, generate normal traffic and reset everything, writing on each run the "ground truth" (`RunRecord`) used for evaluation (T7).

**Suggested profile.** Python. No need to be a blockchain expert: sending a transaction and reading a block go through `backend/chain.py`.

**Concretely, you build:**
- `seed`: the bots' supplies and borrows and the vault positions that make up the reference state; it does nothing if the state is already in place;
- `attack`: forged mint of rsETH (a token minted with no backing), collateral deposit, borrows in tranches, bot rush, protocol freeze by the guardian; tunable by variant (`default`, `slow`, `usdc`) and by seed (`seed`, to replay a draw);
- `normal`: random but harmless benign traffic (supplies, withdrawals, borrows, repayments);
- `reset`: redeploys the contracts (`make deploy FORCE=1`) then reruns the seed;
- the `RunRecord`: one JSON per run in `data/runs/`, with the block of each attack phase;
- the `/api/demo/*` API: the dashboard's "Run attack" and "Reset" buttons (T6).

**At the end, we must be able to:**
1. `make reset && make attack` on local: rsETH backing at 1,935 bps (~19%), 6 borrows of 100 WETH (600 WETH), lend-eth WETH supplied 1,800 / borrowed 1,800 / available 0, rsETH frozen on lend-eth only, lend-avax intact;
2. `make seed` twice in a row: the 2nd sends no transaction (`already_seeded`);
3. `make attack SEED=42` then `SEED=43`: different parameters and two valid `data/runs/*.json`;
4. `make normal MINUTES=2`: runs without exception, returns, and writes a `RunRecord` labelled `normal`;
5. `curl -X POST :8000/api/demo/attack -H 'content-type: application/json' -d '{"seed": null}'`: a `DemoRun` with a seed in [1; 999999], which reaches `done` with its logs; a 2nd call during the run returns 409.

**Key specs.**

| Topic | Rule |
|---|---|
| State after seed | lend-eth WETH 2,000 supplied / 1,200 borrowed, USDC 3,000,000 / 1,800,000; lend-avax WETH 1,000 / 550, USDC 2,000,000 / 1,100,000; rsETH 1,200, backing 10,000 bps |
| Vault after seed | 150 WETH + 400,000 USDC on lend-eth, 100 WETH + 300,000 USDC on lend-avax, 0 pending |
| `default` attack | 5,000 rsETH forged, 100 WETH tranches every 1 s (local) / 8 s (fuji), bot withdrawals after borrows 4 and 5 |
| Seed | `0` = exact default parameters; `≥ 1` = deterministic draw; `null` = the API draws a seed |
| Normal traffic | utilization ≤ 8,500 bps, amount ≤ 10% of available; never any operation on the vault, and the historical borrower (`bots[1]`) does not borrow |

- Oracle prices never changed (no `setPriceE8`); the USDC collateral is deposited before the borrows.
- `seed` and `reset` run under `data/runtime/<network>/maintenance.flag`, removed in a `finally` even on failure.
- Non-circularity: no attack parameter chosen by looking at the rule thresholds.

**Deliverables.** `scenario/common.py`, `params.py`, `seed.py`, `attack.py`, `normal.py`, `reset.py`, `testing.py`, `backend/api/demo.py`, `mk/t2.mk` (`seed`, `attack`, `normal`, `reset`, `test-t2`), tests `backend/tests/test_t2_*.py`.

**Acceptance tests (the ones that matter).**
- T2-30: default attack → `backingRatioBps() == 1935`, lend-eth WETH available 0, rsETH collateral 5,900, lend-avax WETH available 450.
- T2-31: `RunRecord` with 5 phases in the order `forged_mint < collateral_deposit < first_borrow < liquidity_zero < protocol_freeze` and the vault's 4 starting positions.
- T2-32: CLI `--json` → 6 `borrow`, 2 `bot_withdraw` ok and 1 `blocked` (the stuck supplier).
- T2-22: seed rerun → `{"status": "already_seeded"}`, no nonce changed.
- T2-40: normal traffic → utilization ≤ 8,500 at every block, backing always 10,000.
- T2-54: API → 404 unknown run, 409 concurrent run, 422 for `variant="foo"` or `seed=-1`.

**While waiting for the others.** Without contracts (T1), you code and test what does not touch the chain: parameters, planned traffic, `RunRecord`, API with a fake runner; chain tests skip themselves. Missing T0 helpers: shim `scenario/_compat.py`.

**Details for Claude Code.** Detailed sheet T2, section 3 of this document.

---

### T3 · Monitoring: read the chain and raise alerts

**In one sentence.** A program that, at each new block (a "block" = a page of transactions added to the chain), reads the state of the markets where the vault has money and raises an alert as soon as one of the five indicators crosses its threshold.

**Suggested profile.** Python (FastAPI, asyncio). No blockchain knowledge needed: `backend/chain.py` provides the addresses and ABIs (the description of each contract's functions) for the reads.

**Concretely, you build:**
- the **collector** (`collector.py`): reads the two lending markets `lend-eth` and `lend-avax`, the rsETH bridge, the oracle (the price) and the vault, and returns a picture of the state (`Snapshot`), about 20 reads per picture;
- the **5 rules** R1 to R5 (`rules.py`): pure functions that look at the last 20 pictures and return `Alert`s with an English sentence containing the figures;
- the **de-duplication** (`AlertLatch`): an alert is emitted only once per severity, unless its severity goes up;
- the **engine** (`engine.py`): loops every 2 s, collects, applies the rules, stores, and passes new alerts to the response (T4) one at a time, without blocking the API; fallback RPC after 3 errors; paused during maintenance;
- the **state routes** (`api/state.py`): `/api/health`, `/api/state`, `/api/series`, `/api/alerts`, with dollar totals and risk level.

**At the end, we must be able to:**
1. `make replay-t3`: prints exactly 8 alerts (R1 critical at block 45,201,812, exposure $1,325,000; R5 high at block 45,201,878, $775,000); `make replay-t3 FILE=fixtures/snapshots_normal.jsonl` prints nothing;
2. `make monitor-once` on anvil (local test chain) after `make seed`: a JSON `Snapshot` with the vault's 4 positions (150 WETH + 400,000 USDC on `lend-eth`, 100 WETH + 300,000 USDC on `lend-avax`), all 100% withdrawable, total $1,325,000;
3. `ENGINE_ENABLED=true USE_FIXTURES=false make backend` then `make attack` (T2): R1 appears in `/api/alerts` at most 2 polls after the forged mint;
4. after the attack, without T4's response wired in, `/api/state` gives `value_usd` 1,325,000, `withdrawable_usd` 950,000, `at_risk_usd` 375,000, `risk_level` `"critical"`;
5. run `make seed` while the engine is running: no alert; with a bad `RPC_URL`, `/api/health` goes `degraded` and the engine continues on `RPC_FALLBACK_URL`.

**Key specs.**

| Rule | What it looks at | Threshold | Severity |
|---|---|---|---|
| R1 | rsETH backing (`backing_ratio_bps`) | < 9900 bps (99%) | critical |
| R2 | liquidity drop of a market we are exposed to, vs its max over 20 pictures | ≥ 30% / ≥ 60% | high / critical |
| R3 | utilization of a market we are exposed to | ≥ 90% / ≥ 98% | warning / critical |
| R4 | withdrawable share of one of our positions | < 80% / < 50% | high / critical |
| R5 | switch to frozen or paused of a market we are exposed to | transition | high |

- Thresholds in `backend/config/rules.yaml` (exact copy of 2.7); `rules_version` = `"sha256:"` + file hash (71 characters).
- The window = the last 20 **snapshots** (not blocks).
- Maintenance mode: as long as `data/runtime/<network>/maintenance.flag` exists, no rule is evaluated; window cleared when it disappears, and also if `store.generation` changes or the chain goes backwards.
- `/api/state` with no snapshot → `503 {"detail": "no snapshot yet"}`; `value_usd` includes money pulled back to the vault (`idle_usd`), `at_risk_usd` only counts positions.

**Deliverables.** `backend/collector.py`, `backend/rules.py`, `backend/engine.py`, `backend/config/rules.yaml`, `backend/api/state.py`, tests `backend/tests/test_t3_*.py`, `mk/t3.mk` (`test-t3`, `monitor-once`, `monitor`, `replay-t3`).

**Acceptance tests (the ones that matter).**
- Attack series (41 snapshots): 8 alerts in order R1 critical (812), R2 high (826), R2 critical (832), R3 warning + R4 high (836), R3 + R4 critical (838), R5 high (878); no duplicate, nothing on `lend-avax`.
- Normal series: 0 alerts.
- R1 at block 45,201,812: backing 1935 bps, sentence containing `19.4 %`.
- Maintenance: 0 alerts while the file exists, then R1 from the first snapshot after it is removed.
- Slow subscribers: `/api/health` answers in under 0.5 s while a handler sleeps, never two simultaneous calls.

**While waiting for the others.** No chain needed to start: rules, engine and API are developed on `fixtures/snapshots_attack.jsonl` and `snapshots_normal.jsonl`, with a test-local `MemStore` if `backend/store.py` is missing. The collector test stays `skip` until T1 (deployment) and T2 (`make seed`) are ready.

**Details for Claude Code.** Detailed sheet T3, section 3 of this document.

---

### T4 · Response and evidence: decide, put the money in safety, prove it

**In one sentence.** From T3's alerts, the program makes **one** decision fixed by a rule table (the "matrix"), pauses new deposits, pulls back to the vault what is still withdrawable, notifies the humans, then records and anchors a hash of the decision on-chain so an auditor can check it with `verify`.

**Suggested profile.** Python. No need to be a blockchain specialist: `backend/chain.py` sends the transactions (signed operations on the chain), and everything is developed first in dry-run (simulation, no transaction).

**Concretely, you build:**
- the **playbook** `backend/config/playbook.yaml`: the severity → actions matrix (automatic or subject to human approval);
- the **planner**: pure functions (`assess`, `plan_actions`) that turn alerts + snapshot (picture of the state) into a list of actions;
- the **executor**: `Web3Executor` (real transactions with the guardian key) and `DryRunExecutor` (fake, hash `0xdry…`);
- the **notifications**: always log, webhook and SNS if configured, never blocking the withdrawals;
- the **evidence**: file `data/evidence/<id>.json`, hashes `inputs_hash` and `record_hash` (keccak hash), anchoring in `EvidenceRegistry`, and the `verify` command (+ `tamper`/`restore` for the demo);
- the **routes** `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}`.

**At the end, we must be able to:**
1. pass a critical R1 alert at block 45,201,812 and get decision `DEC-fuji-45201812-1`: 8 actions, exposure $1,325,000, case `critical|exposure>=1k|exit_possible`, 4 emergency withdrawals executed (400,000 USDC and 150 WETH on `lend-eth`, 300,000 USDC and 100 WETH on `lend-avax`);
2. run `make verify ID=DEC-fuji-45201812-1` and read `MATCH` (exit code 0);
3. tamper with the evidence using `make tamper` (e.g. `decision.actions.2.params.asset` = `DAI`) then `make verify`: `MISMATCH` (code 1) with readable differences; `make restore` brings back `MATCH`;
4. on anvil (`make chain deploy seed`), see the vault's deposits paused, +700,000 USDC and +250 WETH back in the vault, the hash anchored, then approve `UNPAUSE_DEPOSITS` via the API to lift the pause.

**Key specs.**

| Max severity | Actions, in order |
|---|---|
| critical | NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW per position (auto), OPEN_INCIDENT, UNPAUSE_DEPOSITS (human) |
| high | NOTIFY, PAUSE_DEPOSITS, EMERGENCY_WITHDRAW per position (human), OPEN_INCIDENT |
| warning | NOTIFY only |
| info | nothing, no decision |

- Exposure < $1,000: only NOTIFY if severity is at least high.
- A single decision per snapshot, id `DEC-<network>-<bloc>-<n>`; an already-seen alert triggers nothing; no exception propagates to the engine.
- A failure (e.g. revert `"MiniLend: paused"`) sets the action to `failed` with the reason, the next ones continue.
- `params` never change after planning (otherwise `verify` fails); `unpauseDeposits` is signed with the owner key.

**Deliverables.** `backend/responder.py`, `executor.py`, `notify.py`, `evidence.py`, `cli.py`, `config/playbook.yaml`, `api/response.py`, tests `backend/tests/test_t4_*.py`, `mk/t4.mk` (targets `verify`, `tamper`, `restore`, `test-t4`).

**Acceptance tests (the ones that matter).**
- T4-02: critical R1 at block 45,201,812 → exactly 8 actions, 4 withdrawals in the order `lend-eth` USDC, WETH then `lend-avax` USDC, WETH.
- T4-09: R1 + R2 on the same snapshot → exposure $1,325,000 (not 1,700,000), no double counting.
- T4-17: replaying the same alerts → `[]`; deposits already paused → PAUSE `skipped "already paused"`.
- T4-22: `tamper` then `verify` → `MISMATCH` with `record_hash` and `action[2]`; 2nd tampering → `action count: stored 8 != replanned 7`.
- T4-24: approval via the API → 200 then 409 if replayed, 400 index out of bounds, 404 unknown id, 422 invalid body.
- T4-25 (anvil): real withdrawals, on-chain anchoring and `make verify` → `MATCH`.

**While waiting for the others.** `DRY_RUN_ACTIONS=true`, snapshots read from `fixtures/snapshots_attack.jsonl`, alerts built with `make_alert`, `FakeStore` if `backend/store.py` is missing, empty AWS variables. `make test-t4` must be green with no chain and no AWS (T4-25 skipped).

**Details for Claude Code.** Detailed sheet T4, section 3 of this document.

---

### T5 · Incident and DORA: track the incident and prepare the regulatory report

**In one sentence.** A module that turns the automatic response's decisions (T4) into a tracked incident (status, timeline, amounts saved and still at risk), proposes its DORA classification (the EU regulation on the digital resilience of financial entities) and produces the draft report that a human validates and then submits.

**Suggested profile.** Python, a taste for precise rules. No blockchain knowledge needed: everything is read from the store (the backend's shared memory), and T5 never sends any transaction.

**Concretely, you build:**
- the **incident manager** `IncidentManager`: opens an incident when a decision contains `OPEN_INCIDENT`, attaches subsequent decisions and alerts to it, recomputes amounts, status and timeline;
- the **DORA classification** `classify`: a pure function applying the Art. 9 thresholds and the "major" rule of Art. 8(1) of RTS (EU) 2024/1772, plus the computation of reporting **deadlines** (Regulation (EU) 2025/301);
- the 8-section markdown **report**, with a description written by Bedrock (AWS's AI) if available, otherwise by a fixed text template;
- the **third-party dependency register** (RPC, AWS, oracle, protocols, bridge) with an ok / degraded / down / unknown status;
- the **routes** `/api/incidents`, `/api/incidents/{id}`, `/api/incidents/{id}/report.md`, `POST /api/incidents/{id}/submit`, `/api/dependencies`.

**At the end, we must be able to:**
1. run `make attack SEED=42` on anvil with `USE_FIXTURES=false` and get **exactly one** `contained` incident, `saved_usd` ≈ 1,325,000, `at_risk_usd` 0, classified major with thresholds 9(1) and 9(4);
2. download the report via `GET /api/incidents/{id}/report.md`, or write it to disk with `make dora-report ID=INC-…` (→ `data/reports/INC-….md`);
3. run `make dora-demo` offline and see a complete report;
4. submit via `POST /api/incidents/{id}/submit`: 200 the first time, 409 `already submitted` the second;
5. cut Bedrock: the engine never blocks, the report comes out with the template text.

**Key specs.**

| Point | Rule |
|---|---|
| Art. 9 thresholds (strict comparisons) | 9(1) clients > 10% or > 100,000; 9(3) duration > 24 h or unavailability > 2 h; 9(4) ≥ 2 Member States; 9(6) impact > 100,000 EUR; 9(2), 9(5)(a), 9(5)(b) read from the profile |
| Major (Art. 8(1)) | critical services affected **and** (malicious access 9(5)(b) **or** ≥ 2 distinct criteria); a criterion counts only once |
| Deadlines | initial = min(classification + 4 h, detection + 24 h); intermediate = +72 h; final = +30 days |
| Amounts | `saved_usd` = executed emergency withdrawals; `at_risk_usd` = non-withdrawable share of the affected positions; integer math, never `float(amount)` |
| Status | `contained` after 10 snapshots with no new relevant alert and no blocked position; a high/critical alert ≥ 1,000 USD reopens |

- The classification is only a **proposal**: only a human submits. A `Decision` is never modified.
- Bedrock: call in a separate thread, at most 1 call per second, cache on identical facts, fallback to the text template on error.

**Deliverables.** `backend/incidents.py`, `backend/dora.py`, `backend/llm.py`, `backend/config/dora_profile.yaml`, `backend/config/dependencies.yaml`, `backend/api/incidents.py`, `mk/t5.mk` (`test-t5`, `dora-report`, `dora-demo`), tests `backend/tests/test_t5_*.py`.

**Acceptance tests (the ones that matter).**
- `make test-t5` green (T5-01 to T5-27), with no network and no AWS; each Art. 9 threshold has a boundary test (10 not reached, 10.01 reached).
- Series with reaction: 1 incident `INC-20261011-001`, `contained` at block 45,201,832, `saved_usd` 1,325,000.0, `exposure_usd` 1,325,000.0, `at_risk_usd` 0.0, major `[9(1), 9(4)]`.
- Raw series with no reaction: `open`, `saved_usd` 0.0, `at_risk_usd` 375,000.0, thresholds `[9(1), 9(4), 9(6)]` (345,000 EUR).
- Report: the 8 headings in order, `1,325,000 USD` present, no `None`, `nan` or `TODO`.
- Dependencies on the raw series: `rseth down`, `lend-eth degraded`, `lend-avax ok`.

**While waiting for the others.** Everything works without T3 or T4: in-memory `FakeStore`, hand-built decisions and alerts (`make_decision_r1()`, `make_alert_r1()`), series `fixtures/snapshots_attack.jsonl` and `make_reacted_series()`, empty `BEDROCK_MODEL_ID` (text template).

**Details for Claude Code.** Detailed sheet T5, section 3 of this document.

---

### T6 · Dashboard: show the jury what the platform does

**In one sentence.** A website (`frontend/` folder) that polls the backend every 2 s and shows, in plain English and big numbers, the state of the vault and markets, alerts and decisions, the incident and the DORA report, the evidence for each decision, the metrics and a demo panel; it computes **no** rule, it displays what the API returns.

**Suggested profile.** React + TypeScript. No blockchain knowledge needed: amounts arrive in "base units" (huge integers, e.g. 18 decimals for WETH) that you just convert with `BigInt`.

**Concretely, you build:**
- the **API client** `src/api.ts` and its **mock** `src/fixtureDb.ts`, which serves the `fixtures/*.json` files with no backend at all (`VITE_USE_FIXTURES=true`);
- the **polling hook** `usePolling`: one immediate call, then a call 2 s after the previous one finishes, never two requests at once;
- the **formatting functions** `lib/format.ts` (dollars, units, %, colors, countdowns, UTC) and the labels `lib/labels.ts`;
- the **layout**: sidebar, header (network, block, health), banners FIXTURE MODE / Waiting for first block / Backend unreachable / Data is stale;
- the **8 pages**: `/` Overview, `/charts`, `/alerts`, `/incident`, `/evidence`, `/dependencies`, `/metrics`, `/demo`.

**At the end, we must be able to:**
1. run `make frontend` with no backend (fixtures mode) and see on `http://localhost:5173` the "Total treasury value" card at `$1,325,000`, the `CRITICAL` badge, "Deposits PAUSED" and rsETH backing at `19.4%`;
2. run `make backend` then `VITE_USE_FIXTURES=false make frontend`: the 8 pages render, `/api/state`, `/api/alerts`, `/api/decisions`, `/api/health` are called every 2 s, with no console or CORS error;
3. click **Approve** / **Reject** on a pending action, **Verify** on a decision (green `MATCH` or red `MISMATCH`), **Submit to regulator** on the incident;
4. launch the attack from `/demo` (variant `default`, `slow` or `usdc`, seed) and follow the run log;
5. when `make demo` starts, see "Waiting for first block" while the API answers 503, then the data without reloading the page.

**Key specs.**
- Errors: **503** `no snapshot yet` → grey waiting box (not an outage); **409** → message as is then `refresh()`; 400/404/422 → red message with `detail`.
- Colors = rule thresholds: withdrawable ≥ 80% ok, 50 to 79.99% warn, < 50% bad; utilization < 90% ok, ≥ 98% bad; backing ≥ 99% ok. Color is never the only information (uppercase word).
- Amounts: never `Number` on base units, except `unitsToNumber` for charts; no "bps" on screen, everything in %.
- Metrics: `*_rate` from 0 to 1 (× 100), `*_pct_*` already 0 to 100, `ttd = -1` → `not detected`.
- Demo: empty seed → random integer in [1, 999999]; `0` = default parameters; always send an integer.
- Production: empty `VITE_API_URL` → relative calls `/api/...`; only `EXPLORER_URL` is injected from the root `.env` (which contains private keys).
- `frontend/src/types.ts` belongs to T0: import it, never modify it.

**Deliverables.** `frontend/` (except `src/types.ts`), `frontend/.env.example`, `mk/t6.mk` with `make frontend`, `make frontend-build` (→ `frontend/dist/`), `make test-t6`.

**Acceptance tests (the ones that matter).**
- `make test-t6` green: typecheck, build (no `_PK` or `PRIVATE` in `frontend/dist`), vitest T6-03 to T6-15.
- Overview in fixtures mode: `$1,325,000`, `CRITICAL`, `PAUSED`, `19.4%`, 6 reserve rows; with `positions: []` → "No open positions: all funds are back in the vault.".
- Polling: 1 call on mount, 3 after 4 s; blocked fetcher → only 1 call after 10 s; 0 calls after unmount.
- Approve: exact POST `{"action_index":2,"approver":"jury-demo","approve":true}`; Demo: `Seed 4242` displayed and body `{"seed":4242,"variant":"default"}`.
- Fixtures mode with no backend: `FIXTURE MODE` banner, `fetch` called 0 times, the 8 routes with no exception.

**While waiting for the others.** Everything is first done with `VITE_USE_FIXTURES=true` (T0 fixtures, approval and submission simulated in memory), then against T0's `make backend` skeleton; careful, several fixtures are outdated and will be regenerated: hard-code nothing about their content.

**Details for Claude Code.** Detailed sheet T6, section 3 of this document.

---

### T7 · Evaluation: prove with numbers that the platform works

**In one sentence.** A test bench that runs several attacks and several normal days on the local chain, reads the API as a black box and produces 8 honest numbers: detection, delay, share of the treasury put in safety, false alerts.

**Suggested profile.** Python, comfortable with simple statistics and tests. No blockchain knowledge needed: you only read the HTTP API and JSON files (a "block" is just a number that goes up on the chain).

**Concretely, you build:**
- the **metrics** (`evaluation/metrics.py`): pure functions that, from a run's ground truth (`RunRecord`), alerts and decisions, say whether the attack is detected, in how many blocks (TTD, *time to detect*) and how many dollars are saved;
- the **API client** (`evaluation/api_client.py`): an `EvalApi` interface, its real HTTP version and an in-memory `FakeApi` for tests;
- the **bench** (`evaluation/run_synthetic.py`): freezes the thresholds (sha256 hash of `rules.yaml`), then loops reset → attack → read → compute, then the normal days;
- the **report** (`evaluation/report.py`): writes `data/eval/report.md` with tables, misses and method;
- the **route** `GET /api/metrics`: serves `data/eval/metrics.json`, or the fixture if the file is missing or broken.

**At the end, we must be able to:**
1. run `make eval RUNS=10` (backend started with `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`) and get `metrics.json`, `report.md`, `runs.jsonl` and `rules_frozen.json` in `data/eval/`, with variants `default x4, slow x3, usdc x3`;
2. read in the report 100% detection, a TTD of 0 to 2 blocks, 100% saved versus ~70% for a passive treasury that does not move (71.7 in `default`, 69.8 in `usdc`);
3. call `GET /api/metrics` and find these numbers (never a 500, even on a broken file);
4. see in the notes each miss, false positive or errored run, with no silent retry.

**Key specs.**

| Metric (`synthetic`) | Definition | Format |
|---|---|---|
| `runs_attack`, `runs_normal` | valid runs (errored runs are excluded) | int |
| `detection_rate` | share of attacks with a `critical` alert in the window | 0..1, 3 dec. |
| `false_positive_rate` | share of normal days with an alert ≥ `high` | 0..1, 3 dec. |
| `ttd_blocks_p50`, `ttd_blocks_p90` | 1st critical alert − `attack_start_block`, nearest rank | int, -1 if no detection |
| `saved_pct_mean` | `executed` `EMERGENCY_WITHDRAW` withdrawals / starting value | 0..100, 1 dec. |
| `baseline_saved_pct_mean` | drained reserve = 0%, the others = 100% | 0..100, 1 dec. |

- Run window: `[start_block, end_block + 10]`; anything outside the window is ignored.
- Denominator: 4 positions = **$1,325,000** (150 WETH + 400,000 USDC on `lend-eth`, 100 WETH + 300,000 USDC on `lend-avax`).
- Not counted: statuses other than `executed`, `amount = "0"`, `tx_hash` starting `0xdry…` (dry-run, no funds moved); cap per position.
- Non-circularity: thresholds frozen before the first run; alert with another `rules_version` → stop, exit 3; more than 20% of runs errored → exit 2.

**Deliverables.** `evaluation/metrics.py`, `api_client.py`, `run_synthetic.py`, `report.py`, `backend/api/metrics.py`, `mk/t7.mk` (`make eval`, `eval-report`, `test-t7`, `test-t7-e2e`), tests `backend/tests/test_t7_*.py`; `data/eval/metrics.json` and `report.md` committed.

**Acceptance tests (the ones that matter).**
- T7-04: 4 full withdrawals → `saved_usd == 1325000.0`, `saved_pct == 100.0`; T7-05: only `lend-eth:WETH` executed → 28.3.
- T7-07: drained reserve `lend-eth:WETH` → 71.7; `lend-eth:USDC` → 69.8; none → 100.0.
- T7-10: aggregate → `detection_rate == 0.667`, `false_positive_rate == 0.5`, p50 = 0, p90 = 2, `saved_pct_mean == 66.7`, `baseline_saved_pct_mean == 71.1`.
- T7-17: bench with `FakeApi`, 3 attacks + 1 normal → detection 1.0, p50 = 1, saved 100.0, baseline 71.1, `runs.jsonl` with 4 lines.
- T7-18: alert with another `rules_version` → `SystemExit` code 3.
- T7-20 (`make test-t7-e2e`): `detection_rate == 1.0`, `false_positive_rate == 0.0`, `ttd_blocks_p90 <= 2`, `saved_pct_mean >= 99.0`.

**While waiting for the others.** Everything is developed with no chain and no backend: hand-made `RunRecord`, `Alert` and `Decision`, `FakeApi` for the bench, `fixtures/snapshots_attack.jsonl` and `snapshots_normal.jsonl` for the series, `--no-anchor` for anchoring. T7-16 and T7-20 stay skipped until T2, T3 and T4 are delivered.

**Details for Claude Code.** Detailed sheet T7, section 3 of this document.

---

### T8 · Going live: the demo on AWS, the AWS services and CI

**In one sentence.** Put the platform online on AWS (us-east-1) behind a stable public URL connected to Fuji (Avalanche's test network), provide T4 and T5 with the AWS services they need, and keep `main` green with a CI (tests run automatically on every PR), without ever leaking a key.

**Suggested profile.** Docker, shell and AWS CLI. No blockchain knowledge needed: you package and deploy the others' code.

**Concretely, you build:**
- the **two Docker images**: `sh-backend` (FastAPI API, a single process, with `make` and Foundry so the demo reset can redeploy the contracts) and `sh-frontend` (the dashboard served by nginx, which forwards `/api/*` to the backend);
- the **compose** that runs both, backend bound to `127.0.0.1:8000` only, public on port 80;
- the **AWS resources** described step by step in a runbook: SNS topic (alert e-mails), S3 evidence bucket, Bedrock model (Claude), minimal IAM role, EC2 instance with Elastic IP, secrets in SSM (encrypted parameter store);
- the **deployment script** `infra/deploy.sh` (ships the committed code, assembles the `.env` on the instance, restarts, checks health, rollback);
- `infra/check_aws.py`, which checks that STS, SNS, S3, Bedrock and the public URL respond;
- the GitHub **CI** (5 jobs `python`, `contracts`, `frontend`, `gitleaks`, `docker`) and the anti-secret scan of the images.

**At the end, we must be able to:**
1. open `http://<elastic-ip>/` from a phone on 4G and see the dashboard;
2. run `make aws-smoke HOST=<ip>` and get `OK http network=fuji chain_id=43113 rpc_ok=true engine_running=true` with a block number that increases between two calls 6 s apart;
3. run `make aws-check HOST=<ip>` and get `SUMMARY 4 OK, 0 FAIL, 0 SKIP` (each member receives the "secure-horizons check_aws" e-mail);
4. reboot the instance (`sudo reboot`) and see `make aws-smoke` back to `OK` at most 3 min later with no intervention;
5. open a PR and see the 5 CI jobs green.

**Key specs.**
- uvicorn **without** `--workers` or `--reload`: the engine and the store are in memory, two processes = two withdrawals for the same alert.
- nginx: `proxy_pass http://backend:8000;` **without** a trailing `/`; `/api/demo/` limited to 6 requests/min per IP, 300 s timeout (the reset on Fuji can exceed one minute).
- `infra/fuji.env` (committed, no secret) forces `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`.
- IAM: exactly 7 actions (`sns:Publish`, `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `/healthcheck/*` only, `bedrock:InvokeModel`, `ssm:GetParametersByPath`, `ssm:GetParameter`), no `*` action.
- EC2 `t3.medium`, 30 GB disk, `HttpPutResponseHopLimit=2` (otherwise boto3 in the container finds no credentials); port 22 restricted to the team's `/32` IPs, port 8000 never open.
- Outputs for the others: `SNS_TOPIC_ARN` (topic `secure-horizons-alerts`), `EVIDENCE_BUCKET` (`secure-horizons-evidence-<account_id>`), `BEDROCK_MODEL_ID` copied from `aws bedrock list-inference-profiles`, never typed by hand.
- Never a secret in the repo, an image, `user-data` or a `VITE_*` variable (they end up in clear in the public JS).

**Deliverables.** `infra/` (Dockerfiles and `.dockerignore`, `docker-compose.yml`, `nginx.conf`, `deploy.sh`, `render_env.sh`, `user-data.sh`, `scan_images.sh`, `check_aws.py`, `fuji.env`, `iam-policy.json`, `gitleaks.toml`, `setup-aws.md`, `testdata/frontend-stub/`), `.github/workflows/ci.yml`, `mk/t8.mk` (`deploy-aws`, `aws-check`, `aws-smoke`, `docker-smoke`, `scan-images`, `gitleaks`, `test-t8`…), tests `backend/tests/test_t8_*.py`.

**Acceptance tests (the ones that matter).**
- `make test-t8` green (T8-01 to T8-06, no AWS or network; `check_aws` tested with simulated AWS responses).
- `make docker-smoke`: `localhost/api/health` returns the same JSON as `localhost:8000/api/health`, `localhost/` contains `<div id="root">`, `/api/does-not-exist` → `404` coming from FastAPI.
- `make scan-images` then `--canary`: the fake secret `sh-canary-7f3a9c41` appears in no image.
- `make gitleaks` → `no leaks found` over the whole history.
- `make aws-check` → `SUMMARY 4 OK`; `make aws-smoke` → `OK` with an advancing block; reboot and `make aws-rollback` stay `OK`.

**While waiting for the others.** "Skeleton" deployment with `USE_FIXTURES=true` and `ENGINE_ENABLED=false` (the API serves the fixtures, no contract required), fake front `infra/testdata/frontend-stub/` via `FRONTEND_DIR`. Careful: the health fixture already says `network: fuji`; only `engine_running=true` and an advancing block prove we are really reading Fuji.

**Details for Claude Code.** Detailed sheet T8, section 3 of this document.

---

### T9 · Jury deliverables: README, playbook, compliance, deck, video, pitch, with no made-up number

**In one sentence.** Everything the jury reads, sees and hears (README, response playbook, compliance note, defense sheet, deck outline, video script, pitch), with the code-related parts generated automatically and a checker that rejects any number without a source.

**Suggested profile.** Writing in English, rigor on regulatory texts (DORA, NIST), a bit of Python for the generator and the checker. No blockchain knowledge needed: you just read the files produced by the others.

**Concretely, you build:**
- the **generator** `docs/tools/gen_docs.py` (+ `docs_lib.py`): fills the blocks between `<!-- gen:NAME:start -->` / `<!-- gen:NAME:end -->` markers (Fuji addresses, metrics, response matrix, versions) from the other tasks' files;
- the **checker** `docs/tools/check_docs.py`: every number must come from `data/eval/metrics.json`, `deployments/fuji.json` or `docs/numbers_allowlist.yaml` (with its source); it also detects secrets and reference identifiers;
- the **7 jury documents** in English: `README.md`, `docs/playbook.md`, `docs/compliance.md`, `docs/defense-sheet.md`, `docs/deck-outline.md`, `docs/video-script.md`, `docs/pitch.md`;
- the **source table** `docs/sources.md`: each law article (EUR-Lex links) and each NIST/OWASP/MITRE id cited, with a `Vérifié` column;
- the **smoke test** `docs/tools/fresh_clone_check.sh`: fresh clone, demo, attack, then `make verify` (replays a decision and checks its anchored hash, i.e. written on the blockchain).

**At the end, we must be able to:**
1. run `make docs` on the mocks and see the generated blocks marked PLACEHOLDER (e.g. `[[PLACEHOLDER detection_rate]]`, never "0 %");
2. run `make docs-final` once T1, T4 and T7 are delivered: exit code 0, no PLACEHOLDER or TODO left, real metrics, 9 Fuji addresses with a snowtrace link (the block explorer), playbook generated from the real `backend/config/playbook.yaml`;
3. run `make docs-smoke` on a fresh clone and read `SMOKE OK` on the last line;
4. follow the README Quickstart in exactly 5 commands (`git clone`, `cp .env.example .env`, `make setup`, `make demo`, `make attack SEED=42`);
5. read in `docs/compliance.md` a real output of `make verify ID=DEC-fuji-…` on Fuji (first line `MATCH`, `anchored: yes`).

**Key specs.**

| Deliverable | Constraint |
|---|---|
| Defense sheet | one A4 page, ≤ 600 words; Detect / Respond / Recover, threats, results, limits |
| Deck | 7 to 8 slides (including Live demo, Results, Compliance, Business model), ≤ 3 bullets, speaker note ≤ 40 words |
| Video | 8 to 12 shots, total 120 to 180 s |
| Pitch | Round 1 ≤ 700 words + 10 questions (answer ≤ 50 words); final ≤ 420 words |
| Compliance | slide ≤ 80 words + annex: DORA Art. 17, 18, 19, 28; 4 h / 72 h / 1 month deadlines attributed to Delegated Regulation 2025/301, not to DORA |

- Metric units: `*_rate` in 0..1 (× 100 when displayed), `*_pct_*` already in %, `ttd_blocks_*` = -1 displays "not detected".
- No article or NIST/OWASP/MITRE id cited without reading it on the official source; every business model price is labelled "assumption".
- No secret, no employer name (list in `T9_FORBIDDEN_TERMS`, never committed), no person's name.

**Deliverables.** The 7 documents above, `docs/sources.md`, `docs/numbers_allowlist.yaml`, `docs/assets/`, `docs/tools/*`, `mk/t9.mk` (`make docs`, `docs-check`, `docs-final`, `docs-smoke`, `test-t9`), tests `backend/tests/test_t9_docs.py`.

**Acceptance tests (the ones that matter).**
- Playbook rendered from the mock: critical row exactly `NOTIFY (auto) → PAUSE_DEPOSITS (auto) → EMERGENCY_WITHDRAW (auto) per concerned position → OPEN_INCIDENT (auto) → UNPAUSE_DEPOSITS (human)`; YAML without `matrix` → `ValueError`.
- Fixture metrics: placeholder mode, neither `0 %` nor `0.0`; real sample metrics → `100 %`, `1 block`, `2 blocks`, `Mainnet replay: phase 2`.
- `We save 87 % of funds.` without allowlist → issue reported; `Art. 19`, `2022/2554`, `R1`, `0:42` are not counted as numbers.
- `GUARDIAN_PK=0x` + 64 `a` detected as a secret; a snowtrace link `…/tx/0x…` is not.
- `make test-t9` green with strict tests T9-03, T9-04, T9-06 skipped; those three tests green under `make docs-final`.

**While waiting for the others.** `fixtures/metrics.json` (rendered PLACEHOLDER), `fixtures/deployments.example.json` (sample addresses), `docs/tools/playbook.mock.yaml` and `rules.mock.yaml`, `fixtures/verify.json`, `fixtures/dependencies.json`, the dashboard on fixtures (`USE_FIXTURES=true`) for screenshots, and `TODO(T8): URL` for the AWS URL.

**Details for Claude Code.** Detailed sheet T9, section 3 of this document.

---
## 0. How to use this document

### 0.1 Starting a task with Claude Code

1. Pick your task in "Tasks at a glance" (at the top of this document), clone the repo, create your branch: `git checkout -b tN-nom-court` (e.g. `t3-monitor`).
2. Copy `.env.example` to `.env` and fill in what your task needs (section 2.1).
3. Open Claude Code at the repo root and paste your task's **starter prompt** (at the end of each T section).
4. Your task is done when **all its tests pass** ("Tests that must pass" item) and the "Definition of done" checklist is ticked.

### 0.2 Generic prompt (if your task does not have its own)

```
You are working on task TN of the TASKS.md file (repo root).
1. Read sections 1 and 2 of TASKS.md, then section TN in full.
2. Modify ONLY the files listed under "Owned files" of TN.
   If you need a change elsewhere or in the contract (section 2),
   do not edit: write the request in docs/contract-requests.md and tell me.
3. Work against the listed mocks (fixtures, dry-run, local chain) until
   the other tasks are delivered.
4. Start by writing the tests from "Tests that must pass", then the code.
5. Before each commit: make test-tN (or the given command) must be green.
   Push often (after each green test): the AWS account is wiped at the end of the event.
```

---

## 1. Shared context (everyone reads this)

### 1.1 What we are building

A **DeFi treasury monitoring** platform. Our client is a fund manager who places the funds of their vault (a Safe) in lending protocols. The platform:

1. reads, at every block, the state of the markets where the vault has money and the state of its positions;
2. computes **a few simple indicators** (withdrawable share, utilization, liquidity, collateral backing);
3. raises **explainable alerts** (one sentence with numbers per alert);
4. **reacts** automatically by tightening: pause new deposits, emergency withdrawal to the vault of whatever is still withdrawable;
5. **proves**: every decision is recorded, hashed and its hash anchored on Avalanche Fuji; a `verify` command lets an auditor replay it;
6. opens an **incident** and prepares the pre-filled **DORA report**, which a human validates and sends;
7. shows everything in a **dashboard**.

**Out of MVP (phase 2, do not build now)**: the AI agent proposing allocations, the choice of instructions and of the allowlist, signed mandates, inter-agent security, advanced detection rules (see section 5).

### 1.2 The single scenario (common thread of the demo and the tests)

Synthetic replay of the Kelp/Aave incident of April 18, 2026, **on our own contracts deployed on Fuji** (and on a local anvil chain for tests).

| Phase | What happens on-chain | What the platform must do |
|---|---|---|
| 0. Normal | Bots supply and borrow. The vault has 150 WETH + 400,000 USDC on `lend-eth`, 100 WETH + 300,000 USDC on `lend-avax`. | Nothing (no alert ≥ high). |
| 1. Forged mint | The bridge mints 5,000 rsETH **with no backing**: rsETH backing drops from 100% to ~19%. | **R1 critical** in the next block → pause deposits + emergency withdrawal of all our positions in the deployments that accept rsETH as collateral + incident opened. |
| 2. Fake collateral | The attacker deposits the rsETH as collateral on `lend-eth`. | (already safe) |
| 3. Draining | The attacker borrows the WETH in chunks until none is left. | R2 / R3 if we are still exposed. |
| 4. Rush | Bots try to withdraw their WETH; the last ones stay stuck. | R4 if one of our positions is stuck. |
| 5. Late freeze | The protocol guardian freezes the rsETH reserve. | R5 (context information). |

**The number we want to show**: our withdrawal happens while 100% of the position is still withdrawable, whereas a passive supplier stays stuck.

### 1.3 Architecture

```
            ┌───────────────────────── Avalanche Fuji (or anvil locally) ──────────────────────────┐
            │  MockERC20 (USDC, WETH)   RsETH + MockBridge   MockOracle                             │
            │  MiniLend "lend-eth"      MiniLend "lend-avax"                                        │
            │  TreasuryVault (the vault)                     EvidenceRegistry (hashes)              │
            └───────▲───────────────────────────────▲───────────────────────────────▲──────────────┘
                    │ scripts (T2)                   │ read at every block            │ guardian tx / anchoring
        ┌───────────┴─────────┐          ┌──────────┴──────────────────────────────┴────────────┐
        │ scenario/ (T2)      │          │ backend/ (FastAPI, single process)                     │
        │ seed, attack,       │          │  collector → Snapshot → engine (rules R1..R5) → Alert  │
        │ normal, reset       │          │  → responder (matrix) → Decision → executor (tx)       │
        └─────────────────────┘          │  → evidence (hash, anchoring, verify)                  │
                                         │  → incidents + DORA (report, optional Bedrock)         │
                                         │  API /api/* (T3, T4, T5, T2, T7)                       │
                                         └──────────────▲──────────────────────────▲─────────────┘
                                                        │ HTTP (polling 2 s)       │ SNS, S3, Bedrock
                                         ┌──────────────┴──────────┐      ┌────────┴─────────┐
                                         │ frontend/ (T6) Vite     │      │ AWS (T8)         │
                                         └─────────────────────────┘      └──────────────────┘
            evaluation/ (T7): runs scenarios, reads the API, computes metrics → data/eval/
```

### 1.4 Stack

| Component | Choice |
|---|---|
| Contracts | Solidity 0.8.24, Foundry (`forge`, `anvil`), OpenZeppelin |
| Backend, scenario, evaluation | Python 3.11, FastAPI, Pydantic v2, web3.py ≥ 6.20, PyYAML, boto3, pytest |
| Frontend | Node 20, Vite, React 18, TypeScript, Tailwind, Recharts, Vitest |
| Chain | `local` = anvil (chainId 31337, instant blocks); `fuji` = Avalanche Fuji C-Chain (chainId 43113, ~2 s per block, explorer `https://testnet.snowtrace.io`) |
| Cloud | AWS us-east-1 only: EC2, SNS, S3, Bedrock (Claude models), SSM Parameter Store |

### 1.5 Repo tree and owner of each folder

Each file has **a single owning task**. You only modify your task's files.

```
.
├── TASKS.md                     T0 (this document)
├── CLAUDE.md                    T0 (rules for every Claude Code)
├── README.md                    T9 (final version; each task provides its paragraph in its PR)
├── Makefile                     T0 (includes mk/*.mk; each task has its mk/tN.mk)
├── mk/tN.mk                     TN (make targets of task N)
├── .env.example .gitignore .pre-commit-config.yaml requirements.txt   T0
├── contracts/                   T1 (Foundry project: src/, script/, test/)
├── deployments/<network>.json   T1 (written by the deploy script, committed for fuji)
├── abi/<Contrat>.json           T1 (exported by make abi)
├── scenario/                    T2 (except scenario/__init__.py, created by T0)
├── backend/
│   ├── __init__.py main.py models.py settings.py chain.py store.py fixtures.py   T0 (frozen)
│   ├── collector.py engine.py rules.py config/rules.yaml api/state.py            T3
│   ├── responder.py executor.py notify.py evidence.py cli.py
│   │   config/playbook.yaml api/response.py                                      T4
│   ├── incidents.py dora.py llm.py config/dora_profile.yaml
│   │   config/dependencies.yaml api/incidents.py                                 T5
│   ├── api/demo.py                                                               T2
│   ├── api/metrics.py                                                            T7
│   └── tests/test_tN_*.py                                                        TN (one prefix per task)
├── evaluation/                  T7 (except evaluation/__init__.py, created by T0)
├── frontend/                    T6 (except frontend/src/types.ts, owned by T0: mirror of models.py)
├── fixtures/                    T0 (other tasks may ADD files, never modify existing ones)
├── infra/ .github/workflows/    T8
├── docs/                        T9 (final README, playbook, compliance, defense sheet, deck, video)
│   └── contract-requests.md     everyone (contract change requests)
└── data/                        generated at runtime, ignored by git except data/eval/metrics.json
```

### 1.6 Collaboration rules (anti-friction)

1. **Contract first.** Section 2 of this document, `backend/models.py` and `fixtures/` are frozen. Any change request goes through `docs/contract-requests.md` (see 2.12).
2. **Everyone owns their files.** Never touch a file owned by another task. T0 files only change via the process in 2.12.
3. **Work alone on mocks.** Front on fixtures, detectors on recorded series, response in dry-run, scripts on anvil. Nobody waits for anybody.
4. **Same commands for everyone.** `make <cible>` (section 2.10). Each task adds its targets in its `mk/tN.mk`, never in the root `Makefile`.
5. **Branches and commits.** One branch per task, small PRs to `main`, `make test` green before merge, frequent pushes after each green test (AWS rule: the account is wiped at the end of the event).
6. **Secrets.** No key in the repo (the jury checks). Keys in `.env` (ignored). `gitleaks` in pre-commit. One key per role (2.1), to avoid nonce conflicts.
7. **Language.** Code, names, API, UI, README: English. Internal docs: French.
8. **AWS and Fuji usage rules.** Only test and attack what we deployed ourselves. Synthetic data only. No jailbreaking of Bedrock models. Less than one Bedrock request per second per person.

---

## 2. Interface contract (frozen)

### 2.1 Networks, roles and environment variables

`NETWORK=local` (anvil) or `NETWORK=fuji`. All code reads the environment through `backend/settings.py`.

| Variable | Use | Required by |
|---|---|---|
| `NETWORK` | `local` or `fuji` | all |
| `RPC_URL` | network RPC (local default `http://127.0.0.1:8545`; for fuji, a provider URL, the public RPC is rate-limited) | all |
| `RPC_FALLBACK_URL` | fallback RPC (`https://api.avax-test.network/ext/bc/C/rpc`) | T3, T4 |
| `CHAIN_ID` | 31337 or 43113 (derived from `NETWORK` if missing) | all |
| `EXPLORER_URL` | `https://testnet.snowtrace.io` | T4, T6 |
| `DEPLOYER_PK` | deploys, mints test tokens, sets prices | T1, T2 |
| `OWNER_PK` | vault owner (represents the Safe signers) | T1, T2, T4 |
| `GUARDIAN_PK` | **our platform's** key: pause deposits and emergency withdrawal, nothing else | T4 |
| `PROTOCOL_GUARDIAN_PK` | lending protocol guardian (freeze at the end of the scenario) | T2 |
| `ATTACKER_PK` | attacker | T2 |
| `EVIDENCE_PK` | anchors hashes in `EvidenceRegistry` | T4 |
| `BOT_PKS` | 3 comma-separated keys (normal users) | T2 |
| `USE_FIXTURES` | `true`: the API serves fixtures; `false`: real data | T3, T4, T5 |
| `ENGINE_ENABLED` | `true`: the monitoring loop runs at backend startup | T3 |
| `POLL_INTERVAL_S` | read interval (default 2) | T3 |
| `DRY_RUN_ACTIONS` | `true`: the response sends no transaction | T4 |
| `AWS_REGION` | `us-east-1` | T4, T5, T8 |
| `SNS_TOPIC_ARN` | alerts topic (empty = disabled) | T4, T8 |
| `ALERT_WEBHOOK_URL` | Slack/Discord webhook (empty = disabled) | T4 |
| `EVIDENCE_BUCKET` | S3 evidence bucket (empty = local only) | T4, T8 |
| `BEDROCK_MODEL_ID` | Claude model on Bedrock (empty = report without AI) | T5, T8 |
| `ETH_ARCHIVE_RPC_URL` | Ethereum archive RPC (phase 2, replay of the real incident) | T7 |
| `VITE_API_URL` | API base for the front; empty in production (same origin, nginx serves `/api`), `http://localhost:8000` in development | T6, T8 (in `frontend/.env.example`) |
| `VITE_USE_FIXTURES` | `true`: the front reads `fixtures/` without a backend | T6 |

**On `local`, no key to write**: `settings.private_key(role)` falls back to anvil's public accounts (mnemonic `test test … junk`): deployer = index 0, owner = 1, guardian = 2, protocol_guardian = 3, attacker = 4, evidence = 5, bots = 6, 7, 8.

### 2.2 Solidity contracts (exact interfaces)

All in Solidity 0.8.24, OpenZeppelin for ERC20 and Ownable. Amounts in base units. Errors are `revert`s with the given messages (tests check them).

```solidity
// ---------- Tokens ----------
contract MockERC20 is ERC20, Ownable {          // USDC (decimals 6), WETH (decimals 18)
    constructor(string memory name, string memory symbol, uint8 decimals_) ;
    function mint(address to, uint256 amount) external onlyOwner;
}

contract RsETH is ERC20 {                       // symbol "rsETH", decimals 18
    address public bridge;                      // only minter
    function mint(address to, uint256 amount) external;   // revert "RsETH: only bridge"
    function burn(address from, uint256 amount) external; // revert "RsETH: only bridge"
}

contract MockBridge {                           // simulates the rsETH cross-chain route (LayerZero/OFT style), both ends in one contract (CR-003)
    IERC20 public weth; RsETH public rseth; address public owner;   // owner = deployer (bridge operator)
    uint256 public sourceLocked;                // WETH locked on the source side
    uint256 public destinationReleased;         // rsETH released on the destination side
    uint64 public sourceNonce; uint64 public destinationNonce;
    bool public paused;
    function deposit(uint256 wethAmount) external;               // healthy flow: locks WETH, advances both nonces, releases the same amount of rsETH
    function forgedRelease(address to, uint256 amount) external; // THE FLAW: advances destinationNonce and releases with no source lock (callable by anyone)
    function pause() external;                                   // owner only, idempotent; deposit and forgedRelease then revert "Bridge: paused"
    function conservationGap() external view returns (uint256);  // destinationReleased - sourceLocked (0 if not positive)
    function totalBacking() external view returns (uint256);     // = sourceLocked (display compatibility)
    function backingRatioBps() external view returns (uint256);  // sourceLocked * 10000 / rseth.totalSupply() ; 10000 if supply = 0 (display)
    event Deposited(address indexed user, uint256 amount, uint64 sourceNonce);
    event Released(address indexed to, uint256 amount, uint64 destinationNonce, bool sourceVerified);
    event Paused(address indexed by);
}

contract MockOracle is Ownable {                // USD price with 8 decimals (Chainlink style)
    function setPriceE8(address asset, uint256 priceE8) external onlyOwner;
    function getPriceE8(address asset) external view returns (uint256);   // revert "Oracle: no price"
    event PriceUpdated(address indexed asset, uint256 priceE8);
}

// ---------- Simplified lending protocol (deployed twice: lend-eth, lend-avax) ----------
contract MiniLend {
    struct ReserveData {
        address asset;
        uint256 totalSupplied;       // amount supplied on the lending side (borrowable assets)
        uint256 totalBorrowed;
        uint256 availableLiquidity;  // totalSupplied - totalBorrowed
        uint256 utilizationBps;      // totalBorrowed * 10000 / totalSupplied (0 if nothing)
        uint256 supplyRateBps;       // annualized, indicative (no interest accrual in the MVP)
        uint256 borrowRateBps;
        uint256 totalCollateral;     // amount deposited as collateral (collateral assets)
        uint16  ltvBps;              // 0 if the asset is not collateral
        bool    borrowable;
        bool    frozen;              // freeze: no new deposits or borrows; withdrawals and repayments OK
        bool    paused;              // pause: everything is blocked
    }
    address public protocolGuardian;
    IMockOracle public oracle;

    // Lending side (USDC, WETH)
    function supply(address asset, uint256 amount, address onBehalfOf) external;   // revert "MiniLend: frozen" / "paused" / "not borrowable"
    function withdraw(address asset, uint256 amount, address to) external returns (uint256 withdrawn);
        // amount = type(uint256).max: withdraws min(position, available liquidity), returns 0 without revert if there is nothing to withdraw
        // otherwise: revert "MiniLend: insufficient balance" if amount > position, "MiniLend: insufficient liquidity" if amount > liquidity
    // Collateral side (rsETH)
    function depositCollateral(address asset, uint256 amount) external;            // revert "MiniLend: not collateral" / "frozen"
    function borrow(address asset, uint256 amount) external;
        // check: total borrowed value (oracle) <= collateral value * ltv ; revert "MiniLend: insufficient collateral" / "insufficient liquidity"
    function repay(address asset, uint256 amount) external;                         // capped at the debt
    // Administration (protocolGuardian only, revert "MiniLend: only guardian")
    function listReserve(address asset, bool borrowable, uint16 ltvBps) external;
    function setReserveFrozen(address asset, bool frozen) external;
    function setReservePaused(address asset, bool paused) external;
    function setLtv(address asset, uint16 ltvBps) external;
    // Read
    function getAssets() external view returns (address[] memory);
    function getReservesData() external view returns (ReserveData[] memory);         // one entry per listed asset, in getAssets() order
    function getUserSupplied(address user, address asset) external view returns (uint256);
    function getUserCollateral(address user, address asset) external view returns (uint256);
    function getUserBorrowed(address user, address asset) external view returns (uint256);

    event Supplied(address indexed asset, address indexed from, address indexed onBehalfOf, uint256 amount);
    event Withdrawn(address indexed asset, address indexed user, address to, uint256 amount);
    event CollateralDeposited(address indexed asset, address indexed user, uint256 amount);
    event Borrowed(address indexed asset, address indexed user, uint256 amount);
    event Repaid(address indexed asset, address indexed user, uint256 amount);
    event ReserveListed(address indexed asset, bool borrowable, uint16 ltvBps);
    event ReserveFrozen(address indexed asset, bool frozen);
    event ReservePaused(address indexed asset, bool paused);
    event LtvUpdated(address indexed asset, uint16 ltvBps);
}
// Rate model (identical everywhere, including in the fixtures):
//   U = utilization (0..1). If U <= 0.8: borrow = 100 + 300 * U / 0.8 (bps) ; otherwise borrow = 400 + 7500 * (U - 0.8) / 0.2.
//   supply = borrow * U * 0.85. At U = 100%: borrow = 7900 bps, supply = 6715 bps (the bait yield).

// ---------- The vault (simplified MVP Safe) ----------
contract TreasuryVault {
    address public owner;            // represents the Safe signers
    address public guardian;         // our platform's key: can only tighten
    bool public depositsPaused;
    function supply(address market, address asset, uint256 amount) external;     // owner ; uses the VAULT BALANCE (send tokens to the vault first) ; revert "Vault: deposits paused" / "Vault: only owner"
    function withdraw(address market, address asset, uint256 amount) external;    // owner
    function emergencyWithdraw(address market, address asset) external returns (uint256 withdrawn);
        // owner or guardian ; withdraws min(position, liquidity) TO THE VAULT ITSELF ; returns 0 (and emits the event) if there is nothing to withdraw ;
        // revert "Vault: only guardian or owner" ; revert "MiniLend: paused" if the reserve is paused (the action then becomes failed)
    function pauseDeposits() external;      // owner or guardian ; idempotent (no revert if already paused)
    function unpauseDeposits() external;    // owner only (human decision)
    function setGuardian(address g) external; // owner
    event DepositsPaused(address indexed by);
    event DepositsUnpaused(address indexed by);
    event EmergencyWithdrawal(address indexed market, address indexed asset, uint256 amount, address indexed by);
    event Supplied(address indexed market, address indexed asset, uint256 amount);
    event Withdrawn(address indexed market, address indexed asset, uint256 amount);
}

// ---------- Evidence registry ----------
contract EvidenceRegistry {
    mapping(bytes32 => uint256) public anchoredAt;   // hash -> block number (0 if never anchored)
    function anchor(bytes32 recordHash, string calldata kind, string calldata uri) external;
        // revert "Evidence: already anchored" ; kind ∈ {"decision", "rules", "incident"} ; no access control in the MVP (evidence key by convention)
    event Anchored(bytes32 indexed recordHash, string kind, string uri, address indexed by);
}
```

**Initial deployment parameters** (fixed so that fixtures, tests and demo match):

| Item | Value |
|---|---|
| Oracle prices | USDC = $1.00; WETH = $2,500; rsETH = $2,500 |
| Reserves of `lend-eth` and `lend-avax` | USDC (borrowable and collateral, LTV 8,000 bps), WETH (borrowable and collateral, LTV 8,000 bps), rsETH (collateral only, LTV 7,500 bps). Lending side and collateral side are two separate balances: collateral does not add to borrowable liquidity. |
| Initial liquidity `lend-eth` | WETH: 2,000 supplied of which 150 by the vault, 1,200 borrowed (utilization 60%); USDC: 3,000,000 supplied of which 400,000 by the vault, 1,800,000 borrowed |
| Initial liquidity `lend-avax` | WETH: 1,000 supplied of which 100 by the vault, 550 borrowed; USDC: 2,000,000 supplied of which 300,000 by the vault, 1,100,000 borrowed |
| Collateral of normal borrowers (bots) | `lend-eth`: 900 rsETH + 4,500,000 USDC (capacity $5,287,500 for $4,800,000 borrowed); `lend-avax`: 300 rsETH + 3,000,000 USDC (capacity $2,962,500 for $2,475,000 borrowed) |
| rsETH before the attack | 1,200 in circulation, 1,200 WETH of backing (100%); 900 as collateral on `lend-eth`, 300 on `lend-avax` |
| Default attack | `forgedRelease` of 5,000 rsETH, collateral deposit on `lend-eth`, borrows of 100 WETH per chunk every 8 s until exhausted, 2 withdrawals of 100 WETH by bots during the draining, freeze of rsETH by the protocol guardian at the end of the scenario |

### 2.3 `deployments/<network>.json` file (written by T1, read by everyone)

```json
{
  "network": "fuji",
  "chain_id": 43113,
  "deployed_at_block": 45201700,
  "explorer": "https://testnet.snowtrace.io",
  "assets": { "USDC": "0x…", "WETH": "0x…", "rsETH": "0x…" },
  "contracts": { "MockBridge": "0x…", "MockOracle": "0x…", "TreasuryVault": "0x…", "EvidenceRegistry": "0x…" },
  "lending": [
    { "id": "lend-eth",  "label": "Lending protocol, Ethereum deployment (simulated)",  "address": "0x…" },
    { "id": "lend-avax", "label": "Lending protocol, Avalanche deployment (simulated)", "address": "0x…" }
  ],
  "roles": { "deployer": "0x…", "owner": "0x…", "guardian": "0x…", "protocol_guardian": "0x…",
             "attacker": "0x…", "evidence": "0x…", "bots": ["0x…", "0x…", "0x…"] }
}
```

ABIs: `abi/MockERC20.json`, `abi/RsETH.json`, `abi/MockBridge.json`, `abi/MockOracle.json`, `abi/MiniLend.json`, `abi/TreasuryVault.json`, `abi/EvidenceRegistry.json` (format: the raw JSON ABI list).

### 2.4 Shared Python helpers (`backend/chain.py`, T0)

All Python code goes through these functions (nobody rewrites their own ABI loading or nonce handling).

```python
def w3() -> Web3                                   # client for the current network (RPC_URL)
def load_deployment() -> dict                      # re-reads deployments/<network>.json on every call (a redeploy is picked up)
def load_abi(name: str) -> list                    # abi/<name>.json
def token(symbol: str) -> Contract                 # "USDC" | "WETH" | "rsETH" (ABI MockERC20, RsETH for rsETH)
def lending(deployment_id: str) -> Contract        # "lend-eth" | "lend-avax" (ABI MiniLend)
def vault() -> Contract                            # TreasuryVault
def bridge() -> Contract                           # MockBridge
def oracle() -> Contract                           # MockOracle
def registry() -> Contract                         # EvidenceRegistry
def account(role: str) -> LocalAccount             # "deployer" | "owner" | "guardian" | "protocol_guardian" | "attacker" | "evidence"
def bot_accounts() -> list[LocalAccount]
def send(fn, sender: LocalAccount, value: int = 0) -> dict
    # builds, signs, sends, waits for the receipt; one lock per sender avoids nonce conflicts
    # returns {"tx_hash": "0x…", "status": 1|0, "block_number": int, "gas_used": int}
def explorer_tx(tx_hash: str) -> str               # snowtrace link
```

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

### 2.10 Store and internal wiring (T0 provides the signatures)

```python
# backend/store.py (T0 ; in memory + JSONL writes in data/runtime/<network>/)
class Store:
    def add_snapshot(self, s: Snapshot) -> None
    def latest_snapshot(self) -> Snapshot | None
    def snapshots(self, limit: int = 500) -> list[Snapshot]
    def add_alerts(self, alerts: list[Alert]) -> None
    def alerts(self, since_block: int = 0) -> list[Alert]
    def add_decision(self, d: Decision) -> None
    def update_decision(self, d: Decision) -> None
    def decisions(self) -> list[Decision]
    def get_decision(self, decision_id: str) -> Decision | None
    def upsert_incident(self, i: Incident) -> None
    def incidents(self) -> list[Incident]
    def get_incident(self, incident_id: str) -> Incident | None
    def reset(self) -> None              # empties everything and increments generation
    generation: int                      # reset counter: the engine empties its window when it changes
store = Store()   # single instance imported by everyone

# backend/engine.py (T3)
class Engine:
    def __init__(self, store: Store): ...
    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None   # registers a subscriber
    def process(self, snapshot: Snapshot) -> list[Alert]   # pure: rules over the window, stores, notifies subscribers
    async def run_forever(self) -> None                     # loop: new block → collector → process

# backend/responder.py (T4)
class Responder:
    def __init__(self, store: Store, executor: "Executor"): ...
    def handle(self, alerts: list[Alert], snapshot: Snapshot) -> list[Decision]
    def on_decisions(self, handler: Callable[[list[Decision], list[Alert], Snapshot], None]) -> None

def plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]   # PURE, reused by verify

# backend/incidents.py (T5)
class IncidentManager:
    def __init__(self, store: Store): ...
    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None

# backend/executor.py (T4)
def get_executor() -> Executor   # singleton: DryRunExecutor if DRY_RUN_ACTIONS=true, otherwise Web3Executor
```

Wiring (in `backend/main.py`, T0): `responder = Responder(store, get_executor())`, `engine.on_alerts(responder.handle)` then `responder.on_decisions(incidents.handle)`. `main.py` only mounts and wires the modules that exist: as soon as a task adds its file (for example `backend/responder.py`), it is used with no edit to `main.py`, so no file ever has two authors. A missing module is skipped (its routes answer 404 until then; the dashboard has its own fixture mode meanwhile). A module that exists but fails to import raises.

Shared operating rules:

- **Subscribers outside the loop**: the engine calls subscribers with `await asyncio.to_thread(handler, alerts, snapshot)`, one call at a time, in snapshot order. A slow response (Fuji transactions) therefore blocks neither the API nor the dashboard.
- **Maintenance mode**: as long as the file `data/runtime/<network>/maintenance.flag` exists, the engine keeps reading and storing snapshots but **evaluates no rule**. When the file disappears, or when `store.generation` changes, it empties its window. T2 creates this file at the start of `seed` and `reset` and deletes it at the end (in a `finally`). Without it, setting up the liquidity would look like an attack.

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

---
## 3. Detailed task sheets (for Claude Code)

Every task follows the same outline:
- **Goal**, then what it depends on and what it unblocks;
- **Owned files**;
- **Inputs and outputs**, with the mocks to use meanwhile;
- **Detailed specification**;
- **Tests that must pass** and **definition of done**;
- **Known pitfalls** and **phase 2**;
- **Starter prompt** to paste into Claude Code.

### 3.0 Overview

| Task | What it delivers | Needs (mock meanwhile) | Unblocks |
|---|---|---|---|
| **T0** Foundations | repo skeleton, models, helpers, store, API entry point, fixtures, Makefile, safeguards | nothing | everyone |
| **T1** On-chain contracts | tokens, rsETH bridge with its flaw, oracle, 2 lending protocols, vault with guardian, evidence registry; local and Fuji deployment; ABIs; funding roles with test AVAX | T0 | T2, T3, T4, T7, T8, T9 |
| **T2** Scenario | seed, attack (3 variants, random seed), normal traffic, reset, run ground truth, demo routes | T1 (local chain as soon as `make deploy` works) | T3, T4, T5, T6, T7 |
| **T3** Monitoring | collector, rules R1 to R5, engine, state routes | T1/T2 (`fixtures/snapshots_*.jsonl` series) | T4, T5, T6, T7 |
| **T4** Response and evidence | matrix, on-chain execution, notifications, anchored evidence, `verify`, approvals | T3 (hand-built alerts), T1 (dry-run) | T5, T6, T7, T9 |
| **T5** Incident and DORA | incidents, timeline, DORA classification, report, dependency register | T4 (hand-built decisions) | T6, T9 |
| **T6** Dashboard | all views, drivable demo | T3, T4, T5, T2, T7 (fixtures, then T0 skeleton) | T9 (screenshots, video) |
| **T7** Evaluation | simple metrics on synthetic runs, report | T2, T3, T4 (local chain) | T6, T9 |
| **T8** AWS and CI | images, compose, EC2, SNS, S3, Bedrock, CI, fallback plan | T0 (then everything else for going live) | E2E-3, T9 |
| **T9** Deliverables | README, playbook, compliance, defense sheet, deck, video, pitch | everything (provisional figures marked meanwhile) | the submission |


### T0 · Repo foundations and shared contract

**Goal.** Lay down the shared skeleton so every task can start on its own from minute one: directory tree, data contract in code, blockchain helpers, store, an API entry point that mounts each task's module, consistent fixtures, Makefile, security safeguards. It is **the first commit merged into `main`**; every branch starts from it. The person holding T0 then validates contract change requests (2.12) and coordinates integration (section 4).

**Depends on.** Nothing.

**Unblocks.** All tasks.

**Owned files.**
- Permanently T0: `TASKS.md`, `CLAUDE.md`, `Makefile`, `mk/t0.mk`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `requirements.txt`, `backend/__init__.py`, `backend/api/__init__.py`, `backend/tests/__init__.py`, `scenario/__init__.py`, `evaluation/__init__.py`, `backend/main.py`, `backend/models.py`, `backend/settings.py`, `backend/chain.py`, `backend/store.py`, `backend/fixtures.py`, `fixtures/*`, `frontend/src/types.ts`, `docs/contract-requests.md`, `backend/tests/test_t0_*.py`.
- T0 creates **no file owned by another task**: `backend/main.py` uses the real module (`engine.py`, `responder.py`, `executor.py`, `incidents.py`, `api/state.py`, `api/response.py`, `api/incidents.py`, `api/demo.py`, `api/metrics.py`) as soon as its owning task adds it. `backend/config/rules.yaml` is created by T3 and `backend/config/playbook.yaml` by T4.
- `backend/models.py` and `backend/settings.py` start from the provisional versions written by T4 (contract requests CR-001 and CR-002) and are completed by T0.

**Read before starting.** Sections 1 and 2 in full.

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Interface contract | section 2 of this document | — | — |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `backend/models.py` | Pydantic v2 models from 2.6 | all Python tasks |
| `frontend/src/types.ts` | exact TypeScript mirror of the models (same names, same fields, `string` for amounts, ISO `string` for dates, literal unions for enums) | T6 |
| `backend/settings.py` | variables from 2.1, fallback to anvil accounts locally | all Python tasks |
| `backend/chain.py` | functions from 2.4 | T2, T3, T4, T7 |
| `backend/store.py` | `Store` class from 2.10 + `store` instance | T2, T3, T4, T5, T7 |
| `backend/main.py` | FastAPI app, CORS, 5 routers, wiring from 2.10, engine start if `ENGINE_ENABLED=true` | everyone |
| `fixtures/` | files from 2.13, regenerable with `python -m fixtures._generate` | T3, T4, T5, T6, T7 |
| `Makefile` + `mk/t0.mk` | `include mk/*.mk`, targets `setup`, `backend`, `demo`, `test`, `help`, `test-t0` | everyone |
| `.env.example` | all variables from 2.1, empty values, one comment line each | everyone |
| `CLAUDE.md` | rules for every Claude Code (see step 12) | everyone |

#### Detailed specification

1. **Directory tree.** Create exactly the folders from 1.5, with an `__init__.py` in `backend/`, `backend/api/`, `backend/tests/`, `scenario/`, `evaluation/`, `fixtures/`.

2. **`requirements.txt`** (a single Python environment for backend, scenario, evaluation):
   ```
   fastapi>=0.111
   uvicorn[standard]>=0.30
   pydantic>=2.7
   web3>=6.20,<8
   eth-account>=0.11
   eth-utils>=4
   python-dotenv>=1.0
   pyyaml>=6
   boto3>=1.34
   httpx>=0.27
   pytest>=8
   pytest-asyncio>=0.23
   ```

3. **`backend/models.py`**: the models from 2.6, with the conventions docstring from 2.5. No logic.

4. **`backend/settings.py`**: reads `.env` at the root (python-dotenv), exposes the variables from 2.1, `DEPLOYMENTS_FILE`, `ABI_DIR`, `FIXTURES_DIR`, `DATA_DIR`, `CONFIG_DIR`, `private_key(role)` and `bot_pks()`. In `local`, with no variable set, keys are derived from anvil's public mnemonic (`test test test test test test test test test test test junk`, path `m/44'/60'/0'/0/<index>`, index from 2.1). Nothing is ever written to disk.

5. **`backend/chain.py`**: the functions from 2.4. `token("rsETH")` uses the `RsETH` ABI, other tokens use `MockERC20`. `send()` takes a lock per sender address, reads the `pending` nonce, estimates gas (× 1.3), signs, sends, waits for the receipt (timeout 120 s) and returns `{"tx_hash", "status", "block_number", "gas_used"}`; compatible with web3.py 6 and 7 (`raw_transaction` or `rawTransaction`).

6. **`backend/store.py`**: the class from 2.10, thread-safe (a `threading.RLock`). Data in memory; every append is also written as JSONL in `data/runtime/<network>/` (`snapshots.jsonl`, `alerts.jsonl`, `decisions.jsonl`, `incidents.jsonl`). `snapshots(limit)` keeps at most 2,000 snapshots in memory. `reset()` clears memory and renames the JSONL files with a timestamp suffix. `update_decision` replaces by id; `upsert_incident` inserts or replaces by id.

7. **No stubs.** `backend/store.py` exposes `generation` (integer incremented by `reset()`). T0 writes no placeholder for the other tasks' classes: `main.py` (step 8) only uses the modules that exist.

8. **`backend/main.py`**: creates `app`, adds CORS `*`, mounts `backend/api/<name>.py` for each of `state`, `response`, `incidents`, `demo`, `metrics` that exists (prefix `/api`), builds `engine`, `responder` (with `get_executor()`) and `incidents` from the modules that exist, wires `engine.on_alerts(responder.handle)` and `responder.on_decisions(incidents.handle)` when both sides exist, and on startup launches `engine.run_forever()` if `ENGINE_ENABLED=true`. A missing module is skipped; a module that fails to import raises. A single uvicorn worker (the store is in memory).

9. **Routes**: each task serves its own routes in its own router file, with the fixtures when `USE_FIXTURES=true` (`GET /api/series` reads the `"<deployment_id>:<asset>"` array of `series.json`; `GET /api/incidents` wraps `incident.json` in a list).

10. **Fixtures**: `fixtures/_generate.py` regenerates everything from `models.py`, with rules R1 to R5 from 2.7 and the matrix from 2.8. The story told by the "with reaction" fixtures:
    - block 45,201,812: forged mint of 5,000 rsETH;
    - same block 45,201,812 (block snapshot): critical `R1_BACKING_DROP` alert, exposure $1,325,000, and decision `DEC-fuji-45201812-1` with `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW` (lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH), `OPEN_INCIDENT`, `UNPAUSE_DEPOSITS` pending approval; the transactions are mined in the following blocks;
    - final state: vault paused, 250 WETH + 700,000 USDC pulled back to the vault, no positions left, `at_risk_usd = 0`;
    - incident `INC-20261011-001` contained, DORA major via 9(1) and 9(4);
    - `verify.json` = MATCH, with the decision's real `record_hash`.
    The `snapshots_attack.jsonl` (no reaction) and `snapshots_normal.jsonl` series keep the same market figures; only the USDC and WETH reserves get `ltv_bps = 8000` and the bots' collateral from 2.2 (`total_collateral` USDC = 4,500,000 on `lend-eth`, 3,000,000 on `lend-avax`). `deployments.example.json` follows 2.3 exactly (`assets`, `contracts.MockBridge`, `contracts.MockOracle`…), `run_record.example.json` contains the vault's 4 positions, `demo_run.json` uses the parameters `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals`.

11. **`Makefile`**: `include mk/*.mk` (it does not load `.env`: the Python scripts read it, and the command line wins), `.PHONY`, `help` target (lists targets and their description with `##`), `setup` (`pip install -r requirements.txt`, `npm --prefix frontend install` if `frontend/package.json` exists, `forge install` in `contracts/` if `contracts/foundry.toml` exists), `backend` (a single worker), `demo` (in order: `chain` in the background, `deploy`, `seed`, backend with `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`, `frontend`), `test` (runs `test-t0` to `test-t9` when they exist). `mk/t0.mk` defines `test-t0` = `pytest backend/tests/test_t0_*.py`. No target sets `NETWORK`: it comes from `.env` or the command line.

12. **`CLAUDE.md`** (short, for every Claude Code):
    - read `TASKS.md` sections 1, 2 and your task before any action;
    - only modify the files owned by your task (1.5);
    - the contract (section 2, `models.py`, `fixtures/`, `types.ts`) only changes via `docs/contract-requests.md`;
    - write tests before code, `make test-tN` green before every commit;
    - no keys, no secrets in code, logs or commits;
    - amounts as base-unit strings, rates in bps, dates in UTC ISO;
    - code and UI in English.

13. **Security**: `.gitignore` contains `.env`, `.env.*` except `!.env.example`, `data/runtime/`, `data/evidence/`, `data/runs/`, `data/reports/`, `data/eval/*` except `!data/eval/metrics.json` and `!data/eval/report.md`, `deployments/local.json`, `deployments/*.pending.json`, `node_modules/`, `frontend/dist/`, `frontend/.env*` except `!frontend/.env.example`, `contracts/out/`, `contracts/cache/`, `contracts/broadcast/*/31337/`, `__pycache__/`, `.venv/`. `.pre-commit-config.yaml` runs gitleaks. `.env.example` contains no real values.

14. **`docs/contract-requests.md`**: a request template (task, requested change, reason, impacted tasks, status).

#### Tests that must pass

| Id | Type | Command | Expected result |
|---|---|---|---|
| T0-01 | unit | `pytest backend/tests/test_t0_contract.py::test_fixtures_validate` | each JSON fixture validates against its model (`health`→`Health`, `state`→`StateResponse`, each `series` point→`SeriesPoint`, `alerts`→`Alert[]`, `decisions`→`Decision[]`, `verify`→`VerifyResult`, `incident`→`Incident`, `dependencies`→`Dependency[]`, `metrics`→`EvalMetrics`, `demo_run`→`DemoRun`, `run_record.example`→`RunRecord`) and each line of both `.jsonl` validates as `Snapshot` (41 lines each) |
| T0-02 | unit | `pytest backend/tests/test_t0_contract.py::test_fixture_story` | alerts only use `R1_BACKING_DROP`…`R5_RESERVE_FROZEN`; decision `DEC-fuji-45201812-1` contains exactly the 8 actions listed in step 10, in that order; `incident.saved_usd == 1325000.0`; `state.totals` is `value_usd = 1325000`, `idle_usd = 1325000`, `withdrawable_usd = 0`, `at_risk_usd = 0`; `state.positions == []`; `verify.stored_hash == decisions[R1].record_hash`; `deployments.example.json` has the keys `assets`, `contracts.MockBridge`, `contracts.MockOracle`, `contracts.TreasuryVault`, `contracts.EvidenceRegistry`, `lending`, `roles` |
| T0-03 | unit | `pytest backend/tests/test_t0_contract.py::test_record_hash_recomputes` | recomputing keccak256 of the canonical JSON of the R1 decision (without `record_hash`, `anchor_tx`, `anchor_block`) gives back `record_hash` |
| T0-05 | unit | `pytest backend/tests/test_t0_settings.py::test_local_keys` | with `NETWORK=local` and no key: the address of `account("deployer")` is `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`, that of `guardian` is `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC`, `bot_accounts()` returns 3 accounts; with `NETWORK=fuji` and no key, `private_key("guardian")` raises `RuntimeError` |
| T0-06 | unit | `pytest backend/tests/test_t0_store.py` | append, read, `since_block`, `update_decision`, `upsert_incident`, `reset()` clears everything; JSONL writes to a temporary folder (`DATA_DIR` variable overridden) |
| T0-04 | unit | `pytest backend/tests/test_t0_wiring.py` | `main.py` imports; the router of every task module that exists is mounted (e.g. `/api/decisions` once T4 is merged), and only those |
| T0-08 | manual | `make backend` then `curl -s localhost:8000/api/state` | returns the `state.json` fixture; `localhost:8000/docs` lists all routes from 2.9 |
| T0-09 | manual | `make help` | lists at least `setup backend demo test test-t0` |
| T0-10 | security | `pre-commit run gitleaks --all-files` | no secret found |
| T0-11 | typing | `npx -y -p typescript tsc --noEmit --strict frontend/src/types.ts` | compiles without error |
| T0-12 | unit | `pytest backend/tests/test_t0_contract.py::test_types_ts_mirrors_models` | every Pydantic model has a TypeScript interface in `types.ts` with exactly the same field names |

#### Definition of done

- [ ] All T0 tests pass (`make test-t0`).
- [ ] `main` contains the skeleton; every task can run `make backend` and get fixtures on every route.
- [ ] `.env.example`, `CLAUDE.md`, `docs/contract-requests.md` present.
- [ ] The fixtures tell the story from step 10 and regenerate without error.
- [ ] T0 created no file owned by another task.

#### Known pitfalls

- Keep T0 minimal: shared contract and helpers only, no task logic.
- Anvil keys are public: never write them in a versioned file (gitleaks detects them as private keys).
- `types.ts` must follow `models.py` field by field; a divergence silently breaks the front end. Any model change = regenerate fixtures + types in the same commit.
- Pydantic serialises datetimes with `Z` only if they have a timezone: always create dates with `timezone.utc`.

#### Later (phase 2)

- Generate `types.ts` automatically from FastAPI's OpenAPI (`openapi-typescript`).
- Persistent store (SQLite) if snapshot volume requires it.

#### Claude Code starter prompt

```
You are working on task T0 of TASKS.md (repo root): the shared foundations.
1. Read sections 1 and 2 of TASKS.md, then the T0 section in full.
2. Create exactly the files listed under "Owned files" for T0, and nothing else.
   Never create a file owned by another task.
3. Start with the T0 tests (backend/tests/test_t0_*.py), then the code.
4. make test-t0 must be green; also check T0-08 to T0-11.
5. Push the branch t0-foundations and open a PR to main: once merged, every other task rebases on it.
```


---
### T1 · On-chain contracts

**Goal.** Write, test and deploy (anvil, then Fuji) the 7 contracts of section 2.2, **exactly** with the given signatures, events and revert messages; produce `deployments/<network>.json` (format 2.3) and the ABIs `abi/<Contract>.json`. T1 **deploys and configures** (oracle prices, listed reserves, vault roles) and, on Fuji, **funds the roles with test AVAX** (`make fund-roles`); T1 mints no token and creates no position: that is T2 (`make seed`).

**Depends on.**
- T0 → repo skeleton, root `Makefile` that does `include mk/*.mk`, `.env.example`, `.gitignore` (`contracts/out/`, `contracts/cache/`, `contracts/broadcast/*/31337/`), `backend/settings.py` → meanwhile: run your targets with `NETWORK=local make -f mk/t1.mk <target>` (`mk/t1.mk` never defines `NETWORK`).
- Team / organisers → Fuji `DEPLOYER_PK` key funded with AVAX (faucet); T1 then funds all other roles from the deployer (`make fund-roles`) → meanwhile: **local anvil** only (no key to write, public anvil accounts).
- Nothing else: T1 is the root of the graph, nobody should wait for it long (see "two-step delivery" in 9).

**Unblocks.** T2 (seed, attack, reset call `make deploy`), T3 (collector: `getReservesData`, `backingRatioBps`, `getUserSupplied`, `depositsPaused`), T4 (`pauseDeposits`, `emergencyWithdraw`, `unpauseDeposits`, `anchor`, `anchoredAt`), T7 (evaluation on anvil), T8 (EC2 deployment: Fuji addresses), T9 (addresses and Snowtrace links in the README).

**Owned files.** `contracts/**` (`foundry.toml`, `src/`, `script/`, `test/`, `lib/` via `forge install`), `deployments/**` (`local.json`, `fuji.json`, `fuji.md`, `history/`), `abi/**`, `mk/t1.mk`, `backend/tests/test_t1_deployment.py`.

**Read before starting.** TASKS.md sections 1.2, 1.5, 2.1, **2.2**, **2.3**, 2.4, 2.11; `backend/settings.py` (`ROLE_ENV`, `ANVIL_INDEX`, `private_key`); `backend/chain.py` (`load_abi` accepts a raw list, `contract(name)` reads `contracts[name]`); `fixtures/deployments.example.json` (only the **addresses** matter, its `Bridge`/`Oracle` keys are outdated: section 2.3 is authoritative); last line of `fixtures/snapshots_attack.jsonl` (expected final state of `lend-eth`).

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Interfaces, events, reverts | section 2.2 (frozen) | T0 | — |
| Deployment parameters (prices, reserves, LTV) | table under 2.2 | T0 | — |
| Deployment file format | section 2.3 | T0 | — |
| Roles and keys | `.env`: `DEPLOYER_PK`, `OWNER_PK`, `GUARDIAN_PK`, `PROTOCOL_GUARDIAN_PK`, `ATTACKER_PK`, `EVIDENCE_PK`, `BOT_PKS` (hex, with or without `0x`) | each member / organisers (Fuji) | local: anvil mnemonic `test test … junk`, index 0..8 (2.1) |
| Chain | anvil `127.0.0.1:8545` (31337) or Fuji (43113) via `RPC_URL` | T1 (`make chain`) / RPC provider | anvil |
| Expected addresses on fresh anvil | deployer nonces 0 to 8 = addresses in `fixtures/*.json` | T0 | — |
| Foundry, OpenZeppelin v5.0.2, forge-std | `foundryup`; `forge install` | T1 | — |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `contracts/src/*.sol` | Solidity 0.8.24, one contract per file of the same name | T2 (reading), all |
| `abi/MockERC20.json`, `RsETH.json`, `MockBridge.json`, `MockOracle.json`, `MiniLend.json`, `TreasuryVault.json`, `EvidenceRegistry.json` | **raw JSON ABI list** (`[{"type":"function",…}]`), indent 2, **committed** | T2, T3, T4, T7 via `chain.load_abi` |
| `deployments/local.json` | format 2.3, `network="local"`, `chain_id=31337`, `explorer=""` (not committed) | T2, T3, T4, T7 |
| `deployments/fuji.json` | format 2.3, `chain_id=43113`, `explorer="https://testnet.snowtrace.io"`, **committed** | all, organisers, jury |
| `deployments/fuji.md` | markdown table `Contract | Address | Snowtrace link` | T9 (README), organisers |
| `deployments/history/fuji-<deployed_at_block>.json` | copy of each Fuji deployment (the old `fuji.json` is archived there before any redeployment) | traceability |
| Test AVAX on each Fuji role | `make fund-roles AMOUNT=0.5` (deployer → owner, guardian, protocol_guardian, attacker, evidence, 3 bots) | T2, T4 (their Fuji transactions) |
| Targets `make chain`, `make deploy`, `make abi`, `make fund-roles`, `make test-t1` (+ `t1-*`) | `mk/t1.mk` | all, `make demo` (T0), `make reset` (T2) |

#### Detailed specification

**1. Foundry project.** `cd contracts && forge init --no-git --force .` then `forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts@v5.0.2` (add `--no-commit` if your forge version asks for it). `foundry.toml`:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
evm_version = "shanghai"        # safe on Fuji and anvil (no Cancun opcode)
optimizer = true
optimizer_runs = 200
remappings = ["@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/", "forge-std/=lib/forge-std/src/"]
fs_permissions = [{ access = "read-write", path = "../deployments" }, { access = "read", path = "../fixtures" }]
```

Files: `src/MockERC20.sol`, `src/RsETH.sol`, `src/MockBridge.sol`, `src/MockOracle.sol`, `src/MiniLend.sol`, `src/TreasuryVault.sol`, `src/EvidenceRegistry.sol`, `src/interfaces/IMockOracle.sol`, `src/interfaces/IMiniLend.sol`; `script/Deploy.s.sol`, `script/deploy.sh`, `script/export_abi.py`, `script/check_deployment.py`, `script/fund_roles.py`; `test/*.t.sol`, `test/utils/BaseTest.sol`, `test/harness/MiniLendHarness.sol`. Transfers via `SafeERC20`. Revert messages: exact strings, with `require(cond, "MiniLend: frozen")`.

**2. Tokens.**
- `MockERC20(name, symbol, decimals_)`: `ERC20(name, symbol)`, `Ownable(msg.sender)`, `decimals()` overridden. `mint` `onlyOwner` (OZ v5: reverts with custom error `OwnableUnauthorizedAccount(address)`, no string). Deployed: `("USD Coin (mock)", "USDC", 6)`, `("Wrapped Ether (mock)", "WETH", 18)`.
- `RsETH(address bridge_)`: `ERC20("Restaked ETH (mock)", "rsETH")`, 18 decimals, immutable `bridge`. `mint`/`burn`: `require(msg.sender == bridge, "RsETH: only bridge")`.
- `MockBridge(IERC20 weth_, RsETH rseth_)`: `deposit(a)` = `weth.safeTransferFrom(msg.sender, this, a)`, `totalBacking += a`, `rseth.mint(msg.sender, a)`, emits `Deposited(msg.sender, a)` **then** `Released(msg.sender, a, true)`. `forgedRelease(to, a)` = `rseth.mint(to, a)` without touching `totalBacking`, emits `Released(to, a, false)`, **no access control** (that is the flaw). `backingRatioBps()` = `supply == 0 ? 10000 : totalBacking * 10000 / supply` (integer division, implicit cap: can exceed 10000 if someone burns, irrelevant).
- RsETH/Bridge chicken-and-egg: the script **predicts** the bridge address (`vm.computeCreateAddress(deployer, vm.getNonce(deployer) + 1)`), deploys `RsETH(predicted)`, then `MockBridge(weth, rseth)` and `require(address(bridge) == predicted, "Deploy: bridge address mismatch")`.

**3. `MockOracle`** (`Ownable(msg.sender)`): `mapping(address => uint256) priceE8`. `setPriceE8` emits `PriceUpdated`. `getPriceE8`: `require(p > 0, "Oracle: no price")` (price 0 = no price).

**4. `MiniLend(address oracle_, address protocolGuardian_)`.** State: `address[] assets`; `mapping(address => Reserve)` (`listed`, `decimals` read via `IERC20Metadata` at listing, `totalSupplied`, `totalBorrowed`, `totalCollateral`, `ltvBps`, `borrowable`, `frozen`, `paused`); `supplied[user][asset]`, `collateral[user][asset]`, `borrowed[user][asset]`. No accrued interest, no liquidation, no collateral withdrawal (not in 2.2).
- `onlyGuardian`: `require(msg.sender == protocolGuardian, "MiniLend: only guardian")`.
- `listReserve(asset, borrowable, ltv)`: 1st call → push into `assets`; a later call on the same asset → updates `borrowable`/`ltvBps` **without duplicate**. Emits `ReserveListed`. `setReserveFrozen`/`setReservePaused`/`setLtv` emit their events.
- Order of checks (the first that fails wins, the tests verify it):

| Function | Checks, in order | Effect |
|---|---|---|
| `supply(asset, amount, onBehalfOf)` | `paused` → `frozen` → `!listed \|\| !borrowable` = `"MiniLend: not borrowable"` | `transferFrom(msg.sender)`, `supplied[onBehalfOf] += amount`, `totalSupplied += amount`, `Supplied(asset, msg.sender, onBehalfOf, amount)` |
| `withdraw(asset, amount, to)` | `paused`; if `amount == type(uint256).max`: `w = min(supplied[msg.sender], liquidity)`; otherwise `amount > supplied[msg.sender]` → `"MiniLend: insufficient balance"` (2.2), then `amount > liquidity` → `"MiniLend: insufficient liquidity"` | **allowed if frozen**; `w == 0` → returns 0 with no transfer or event; otherwise decrements, `transfer(to, w)`, `Withdrawn(asset, msg.sender, to, w)`, returns `w` |
| `depositCollateral(asset, amount)` | `paused` → `frozen` → `!listed \|\| ltvBps == 0` = `"MiniLend: not collateral"` | `transferFrom(msg.sender)`, `collateral[msg.sender] += amount`, `totalCollateral += amount`, event. **Separate balance**: touches neither `totalSupplied` nor liquidity (USDC collateral never becomes borrowable) |
| `borrow(asset, amount)` | `paused` → `frozen` → `"not borrowable"` → `amount > liquidity` = `"MiniLend: insufficient liquidity"` → health = `"MiniLend: insufficient collateral"` | `borrowed += amount`, `totalBorrowed += amount`, transfer, `Borrowed` |
| `repay(asset, amount)` | `paused` | `r = min(amount, borrowed[msg.sender])`, `transferFrom` of `r` only, decrements, `Repaid(asset, msg.sender, r)`; **allowed if frozen** |

  `liquidity = totalSupplied - totalBorrowed` (accounting, never `balanceOf`: a token donation or deposited USDC/WETH collateral changes nothing). The liquidity check comes **before** the health check: T2's attacker knows it has drained everything when it gets `"insufficient liquidity"`.
- Health (`borrow`): `valE8(a, x) = x * oracle.getPriceE8(a) / 10**decimals(a)`. Condition: `(Σ_a valE8(a, borrowed[user][a]) + valE8(asset, amount)) * 10000 <= Σ_a valE8(a, collateral[user][a]) * ltvBps(a)`. Equality accepted. The sum covers **all** listed assets with `ltvBps > 0` (rsETH 7,500, USDC and WETH 8,000): this is what makes the 2.2 seed feasible without touching prices. Frozen collateral still counts. An asset without a price reverts with `"Oracle: no price"`.
- Rate model (integers, identical to 2.2) in `function _rates(uint256 u) internal pure returns (uint256 supplyBps, uint256 borrowBps)`:
  `b = u <= 8000 ? 100 + 300 * u / 8000 : 400 + 7500 * (u - 8000) / 2000`; `s = b * u * 85 / 1_000_000`. `u = totalSupplied == 0 ? 0 : totalBorrowed * 10000 / totalSupplied`. **Non-borrowable** reserve → `(0, 0)`.
  Reference values: u=0 → (0, 100); 5500 → (143, 306); 6000 → (165, 325); 8000 → (272, 400); 9000 → (3174, 4150); 9800 → (5955, 7150); 10000 → (6715, 7900).
- `getReservesData()`: one `ReserveData` per asset in `getAssets()` order, fields **in the exact order of 2.2** (T3 decodes by name via the ABI); `availableLiquidity`, `utilizationBps`, `supplyRateBps`, `borrowRateBps` computed on the fly.

**5. `TreasuryVault(address owner_, address guardian_)`.**
- `supply(market, asset, amount)`: `"Vault: only owner"` then `"Vault: deposits paused"`; funds taken from the **vault balance** (never `transferFrom(owner)`: T2 first mints or sends the tokens to the vault; insufficient balance → OZ v5 ERC20 revert `ERC20InsufficientBalance`); `forceApprove(market, amount)`; `IMiniLend(market).supply(asset, amount, address(this))`; `Supplied(market, asset, amount)`.
- `withdraw(market, asset, amount)`: owner; `IMiniLend(market).withdraw(asset, amount, address(this))`; `Withdrawn(market, asset, w)`. Works even if `depositsPaused`.
- `emergencyWithdraw(market, asset)`: owner or guardian, otherwise `"Vault: only guardian or owner"`; `w = withdraw(asset, type(uint256).max, address(this))`; **destination is always the vault** (no `to` parameter); emits `EmergencyWithdrawal(market, asset, w, msg.sender)` even if `w == 0` (zero position or zero liquidity: **no revert**); returns `w`. A `paused` reserve bubbles up `"MiniLend: paused"` (T4 marks the action `failed`).
- `pauseDeposits()`: owner or guardian, **idempotent** (2nd call does not revert, re-emits `DepositsPaused`). `unpauseDeposits()`: owner only (`"Vault: only owner"`). `setGuardian(g)`: owner only.
- The vault has no function to send tokens out to a third-party address (MVP).

**6. `EvidenceRegistry`.** `anchor(h, kind, uri)`: `require(anchoredAt[h] == 0, "Evidence: already anchored")`, `anchoredAt[h] = block.number`, `Anchored(h, kind, uri, msg.sender)`. No access control and no on-chain validation of `kind` (convention `decision|rules|incident` enforced by T4).

**7. `script/Deploy.s.sol`** (`contract Deploy is Script`).
- `function run() external` = `Roles memory r = loadRoles(); Deployed memory d = deployAll(r); _write(d, r);`; `deployAll` is `public` so it can be called from `Deploy.t.sol` without writing a file.
- `loadRoles()` reproduces **exactly** `settings.private_key`: for each role, `vm.envOr(ROLE_ENV, string(""))`; non-empty → `vm.parseUint` (prefix `0x` if missing); empty and `block.chainid == 31337` → `vm.deriveKey("test test test test test test test test test test test junk", ANVIL_INDEX)`; empty on Fuji → `revert("Deploy: missing <VAR>")`. Bots: empty `BOT_PKS` locally → index 6, 7, 8. Only the `deployer` and `protocol_guardian` keys sign; the others are only used to compute `vm.addr(pk)`. No key is ever logged (`console.log` of addresses only).
- Safeguard: `NETWORK=fuji` and `block.chainid != 43113` (or `local` and `!= 31337`) → `revert("Deploy: chain id mismatch")`.
- **Mandatory** order (deterministic addresses on fresh anvil = fixture addresses): `vm.startBroadcast(deployerPk)` → nonce 0 USDC `0x5FbDB2315678afecb367f032d93F642f64180aa3`, 1 WETH `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`, 2 RsETH `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`, 3 MockBridge `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`, 4 MockOracle `0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9`, 5 MiniLend lend-eth `0x5FC8d32690cc91D4c39d9d3abcBD16989F875707`, 6 MiniLend lend-avax `0x0165878A594ca255338adfa4d48449f69242Eb8F`, 7 TreasuryVault `0xa513E6E4b8f2a923D98304ec87F64353C4D5C853`, 8 EvidenceRegistry `0x2279B7A0a67DB372996a5FaB50D91eAA73d2eBe6`; **only then** `setPriceE8` USDC `1e8`, WETH `2500e8`, rsETH `2500e8`; `stopBroadcast`. Then `vm.startBroadcast(protocolGuardianPk)`: on each MiniLend, `listReserve(USDC, true, 8000)`, `listReserve(WETH, true, 8000)`, `listReserve(rsETH, false, 7500)` (this order = `getAssets()` order). MiniLend: `protocolGuardian = roles.protocol_guardian`, `oracle = MockOracle`. Vault: `owner = roles.owner`, `guardian = roles.guardian`.
- `deployed_at_block` = `block.number` read at the start of `run()` (≤ actual block of the 1st deployment: T3 can scan events from there).
- Writing: nested objects via `vm.serializeAddress`/`vm.serializeString` (a valid JSON string passed to `serializeString` is inserted as an object); `lending` built with `string.concat("[", l1, ",", l2, "]")`; `roles.bots` via `vm.serializeAddress(key, "bots", address[])`. File written: `deployments/<network>.pending.json` (**never directly** `<network>.json`, see pitfall no. 1). Keys: `network`, `chain_id`, `deployed_at_block`, `explorer`, `assets{USDC,WETH,rsETH}`, `contracts{MockBridge,MockOracle,TreasuryVault,EvidenceRegistry}`, `lending[{id,label,address}]` (exact labels from 2.3), `roles{deployer,owner,guardian,protocol_guardian,attacker,evidence,bots[3]}`.

**8. Helper scripts.**
- `script/check_deployment.py --network N --rpc-url URL --promote` (stdlib + `urllib`, no `backend` import): validates the schema (exact keys, `0x` + 40 hex checksummed addresses, 2 lending entries in the order `lend-eth`, `lend-avax`, 3 bots), checks `eth_getCode != "0x"` for the 9 contract addresses, rewrites the JSON with indent 2 in 2.3 order, renames `.pending.json` → `<network>.json`; on Fuji also copies to `deployments/history/fuji-<deployed_at_block>.json` and regenerates `deployments/fuji.md`. Otherwise exit 1 with a clear message (the previous `.json` stays intact).
- `script/export_abi.py`: for the 7 names, reads `contracts/out/<Name>.sol/<Name>.json`, writes `abi/<Name>.json` = `data["abi"]` (`json.dump(indent=2)`). No `forge inspect` (its output format changes between versions).
- `script/deploy.sh` (called by `make deploy`): stores the `NETWORK` it received (the root `Makefile` exports it from `.env` or the command line; empty → exit 1 "NETWORK not set: put it in .env or run NETWORK=local make deploy"), loads `../.env` if it exists (`set -a; . .env; set +a`, **never** `set -x`) for direct runs of the script, re-imposes the received `NETWORK`; local → RPC `http://127.0.0.1:8545`, checks `cast chain-id` (otherwise "anvil is not responding: run `make chain`"); fuji → **first** (before any network call): if `deployments/fuji.json` exists and `FORCE != 1` → exit 1 "a Fuji deployment already exists: addresses will change, warn the team then rerun with FORCE=1"; with `FORCE=1`, archives the old file to `deployments/history/fuji-<deployed_at_block>.json` (without overwriting an existing archive) before deploying; then `RPC_URL` required, adds `--slow`; then `forge script script/Deploy.s.sol:Deploy --rpc-url "$RPC" --broadcast`, `check_deployment.py --promote`, `export_abi.py`, prints the addresses (and Snowtrace links on Fuji). `RESUME=1` → adds `--resume` (same forge command). 1st argument `verify-src` → runs `forge verify-contract` (see 10) for the 9 contracts from `deployments/fuji.json`. No key as a command-line argument (`forge` reads the keys via `vm.envOr` in the script).
- `script/fund_roles.py --amount 0.5` (called by `make fund-roles AMOUNT=0.5`): **Fuji only** (`NETWORK != fuji` → exit 1 "useless locally: anvil accounts already have 10,000 ETH"); reads role addresses from `deployments/fuji.json` (`owner`, `guardian`, `protocol_guardian`, `attacker`, `evidence`, `bots[3]`, never `deployer`); if the file does not exist yet (first deployment: the `protocol_guardian` must have AVAX **before** `make deploy` to sign the `listReserve` calls), derives them from the `.env` keys via `backend.settings.private_key(role)` (same addresses). Sends from `DEPLOYER_PK` (web3 + `eth_account`, key read from the environment, never as an argument or in logs) a transfer of `AMOUNT` AVAX to each role whose balance is below `AMOUNT` (a role already served is skipped: rerunning does not drain the faucet); one transaction at a time, waits for the receipt; first checks that the deployer has `8 × AMOUNT` + 0.2 AVAX of margin, otherwise exit 1 with the missing amount; prints a table `role | address | balance before | sent | balance after`.

**9. `mk/t1.mk`** (unique targets, `t1-` prefix for helpers; **never defines `NETWORK`**: it comes from `.env` or the command line via the root `Makefile`, which does `-include .env` and `export`):

```make
.PHONY: chain deploy abi fund-roles test-t1 t1-build t1-resume t1-links t1-verify-src
chain:            ## local anvil, 1 block/s, chainId 31337
	anvil --block-time 1 --chain-id 31337
t1-build:
	cd contracts && forge build
deploy: t1-build  ## deploys to $(NETWORK), writes deployments/$(NETWORK).json and abi/
	@NETWORK=$(NETWORK) FORCE=$(FORCE) bash contracts/script/deploy.sh
abi: t1-build     ## exports abi/<Contract>.json
	@python3 contracts/script/export_abi.py
fund-roles:       ## Fuji: sends AMOUNT AVAX from the deployer to each role (default 0.5)
	@NETWORK=$(NETWORK) python3 contracts/script/fund_roles.py --amount $(or $(AMOUNT),0.5)
test-t1: t1-build ## Solidity tests + Python smoke test
	cd contracts && forge test -vv
	python -m pytest backend/tests/test_t1_deployment.py -q
t1-resume:        ## resumes an interrupted Fuji deployment (forge script --resume)
	@NETWORK=fuji RESUME=1 bash contracts/script/deploy.sh
t1-links:         ## prints deployments/fuji.md
	@cat deployments/fuji.md
t1-verify-src:    ## verifies the source on Snowtrace (routescan), optional
	@NETWORK=fuji bash contracts/script/deploy.sh verify-src
```

**Two-step delivery.** (a) As soon as the interfaces compile: push the 7 `abi/*.json` and a working local `make deploy` (even with few tests), to unblock T2, T3 and T4. (b) Then: all the tests, then Fuji.

**10. Fuji.** Cost: ~9 deployments + 3 prices (deployer) + 6 listings (protocol_guardian), on the order of 10 M gas; plan ~0.5 AVAX of deployment on the deployer and ~0.1 on the protocol_guardian (wide margin). **Only the deployer is funded externally**: faucet `https://core.app/tools/testnet-faucet/` (daily limit, sometimes conditional; ask the organisers whether they hand out test AVAX), aim for ~5 AVAX. **T1 funds all the other roles** (owner, guardian, protocol_guardian, attacker, evidence, bots): `make fund-roles AMOUNT=0.5` (8 × 0.5 = 4 AVAX), rerunnable at any time to top up a dry role (T2 and T4 ask T1 for it). Order on Fuji: faucet → deployer, `make fund-roles AMOUNT=0.5`, `make deploy` (then `FORCE=1 make deploy` for a redeployment, the old file goes to `history/`). RPC: the public `https://api.avax-test.network/ext/bc/C/rpc` is rate-limited → `RPC_URL` from a provider; `--slow` (one tx at a time, waits for the receipt); on interruption, `make t1-resume` (`forge script … --resume`) then `check_deployment.py --promote`. Source verification (optional, appreciated by the jury): `forge verify-contract <addr> src/MiniLend.sol:MiniLend --chain-id 43113 --verifier-url 'https://api.routescan.io/v2/network/testnet/evm/43113/etherscan' --etherscan-api-key verifyContract --constructor-args $(cast abi-encode "constructor(address,address)" <oracle> <pg>)`. Commit `deployments/fuji.json` and `fuji.md` to the repo (organisers' request) and warn the team at each redeployment.

#### Tests that must pass

Global command: `make test-t1` (= `cd contracts && forge test -vv` then `pytest backend/tests/test_t1_deployment.py -q`). A single function: `cd contracts && forge test --mt <name> -vvv`. `test/utils/BaseTest.sol` provides: tokens, oracle at 2.2 prices, a MiniLend listed as in 2.2 (USDC and WETH borrowable, LTV 8000; rsETH collateral only, LTV 7500), actors `pg`, `owner`, `guardian`, `alice`, `bob`, `carol`, `attacker`, helpers `_mint(sym, to, amt)`, `_supply(user, asset, amt)`, `_collat(user, amt)` (rsETH via `bridge.deposit`, hence backed), `_collatAsset(user, asset, amt)` (USDC or WETH collateral), `_seed(market, wethSup, usdcSup, rsethCol, usdcCol, wethBor, usdcBor)` (2.2 initial state of a deployment).

| Id | File :: test | Setup | Expected result |
|---|---|---|---|
| T1-01 | `Tokens.t.sol::test_MockERC20_metadata` | BaseTest deployment | USDC `decimals()==6`, symbol `"USDC"`; WETH `18`, `"WETH"` |
| T1-02 | `Tokens.t.sol::test_MockERC20_mint_onlyOwner` | `alice` calls `mint` | revert `OwnableUnauthorizedAccount(alice)`; owner mints 5e6 → `balanceOf==5e6` |
| T1-03 | `Tokens.t.sol::test_RsETH_onlyBridge` | `alice` calls `mint` then `burn` | both revert `"RsETH: only bridge"`; prank bridge → mint/burn OK; `symbol()=="rsETH"`, `decimals()==18` |
| T1-04 | `MockBridge.t.sol::test_backingRatio_emptySupply` | no deposit | `backingRatioBps()==10000` |
| T1-05 | `MockBridge.t.sol::test_deposit_backed` | `alice` deposits 1200e18 WETH | `totalBacking==1200e18`, `rseth.totalSupply()==1200e18`, `weth.balanceOf(bridge)==1200e18`, ratio `10000`, events `Deposited(alice,1200e18)` and `Released(alice,1200e18,true)` |
| T1-06 | `MockBridge.t.sol::test_forgedRelease_unbacked` | T1-05 then `attacker` `forgedRelease(attacker, 5000e18)` | supply `6200e18`, backing `1200e18`, **ratio `1935`**, event `Released(attacker,5000e18,false)`; callable by anyone |
| T1-07 | `MockBridge.t.sol::test_backingRatio_half` | deposit 1000e18 + forged 1000e18 | ratio `5000` |
| T1-08 | `MockOracle.t.sol::test_price_roundtrip_and_errors` | | `setPriceE8(WETH,2500e8)` → `getPriceE8==2500e8` + `PriceUpdated`; unknown asset → `"Oracle: no price"`; `alice` sets → `OwnableUnauthorizedAccount` |
| T1-09 | `MiniLend.t.sol::test_admin_onlyGuardian` | `alice` | `listReserve`, `setReserveFrozen`, `setReservePaused`, `setLtv` → `"MiniLend: only guardian"`; by `pg` → events `ReserveListed`, `ReserveFrozen`, `ReservePaused`, `LtvUpdated` |
| T1-10 | `MiniLend.t.sol::test_listReserve_orderNoDuplicate` | relist WETH `(false, 100)` | `getAssets()==[USDC,WETH,rsETH]` (length 3), WETH `borrowable==false`, `ltvBps==100` |
| T1-11 | `MiniLend.t.sol::test_supply_and_onBehalfOf` | `alice` supplies 2000e18 WETH for `bob` | `getUserSupplied(bob,WETH)==2000e18`, alice 0, `totalSupplied==2000e18`, event `Supplied(WETH,alice,bob,2000e18)` |
| T1-12 | `MiniLend.t.sol::test_supply_reverts` | | rsETH → `"MiniLend: not borrowable"`; unlisted token → same; WETH frozen → `"MiniLend: frozen"`; WETH paused → `"MiniLend: paused"` |
| T1-13 | `MiniLend.t.sol::test_rates_60pct` | supply 2000e18 WETH; borrower `_collat` 2000e18 rsETH, borrow 1200e18 | `totalBorrowed==1200e18`, `availableLiquidity==800e18`, `utilizationBps==6000`, `supplyRateBps==165`, `borrowRateBps==325` |
| T1-14 | `MiniLend.t.sol::test_rates_55pct` | supply 1000e18, borrow 550e18 | `5500`, `143`, `306` |
| T1-15 | `MiniLend.t.sol::test_rates_100pct` | supply 1000e18, borrow 1000e18 | `availableLiquidity==0`, `10000`, **`6715`**, **`7900`** |
| T1-16 | `MiniLend.t.sol::test_rateModel_table` | `MiniLendHarness.exposedRates(u)` | u=0 → (0,100); 8000 → (272,400); 9000 → (3174,4150); 9800 → (5955,7150); 10000 → (6715,7900); rsETH (non-borrowable) → `(0,0)` in `getReservesData` |
| T1-17 | `MiniLend.t.sol::test_borrow_collateralLimit` | `_collat` 100e18 rsETH ($250,000, capacity $187,500), ample liquidity | borrow 75e18 WETH OK (equality); then borrow 1e6 USDC → `"MiniLend: insufficient collateral"` |
| T1-18 | `MiniLend.t.sol::test_borrow_multiAssetDecimals` | same collateral | borrow 50e18 WETH + 62_500e6 USDC OK; +1e6 USDC → `"MiniLend: insufficient collateral"` |
| T1-19 | `MiniLend.t.sol::test_borrow_liquidityBeforeCollateral` | supply 100e18 WETH, borrower **without** collateral | borrow 101e18 → `"MiniLend: insufficient liquidity"`; borrow rsETH → `"MiniLend: not borrowable"` |
| T1-20 | `MiniLend.t.sol::test_depositCollateral_reverts` | | unlisted token → `"MiniLend: not collateral"`; WETH after `setLtv(WETH,0)` → `"MiniLend: not collateral"`; rsETH frozen → `"MiniLend: frozen"`; paused → `"MiniLend: paused"`; OK → `totalCollateral` +x, `getUserCollateral` +x, event; USDC collateral 1_000_000e6 → USDC `totalSupplied` and `availableLiquidity` **unchanged** |
| T1-21 | `MiniLend.t.sol::test_withdraw_exact_and_errors` | alice position 150e18, reserve liquidity 100e18 | `withdraw(50e18)` returns `50e18` + `Withdrawn(WETH,alice,alice,50e18)` (position 100e18, liquidity 50e18); `withdraw(101e18)` → `"MiniLend: insufficient balance"` (checked **before** liquidity); `withdraw(100e18)` → `"MiniLend: insufficient liquidity"`; `carol` with no position `withdraw(1)` → `"MiniLend: insufficient balance"` |
| T1-22 | `MiniLend.t.sol::test_withdrawMax_minPositionLiquidity` | 3 cases | liquidity 800 / position 150 → returns `150e18`; liquidity 100 / position 150 → `100e18`, remaining position `50e18`; liquidity 0 → returns `0`, no revert, balance unchanged; user **with no position** (liquidity 800) → returns `0`, no revert, no `Withdrawn` event (`vm.recordLogs`) |
| T1-23 | `MiniLend.t.sol::test_frozen_allowsWithdrawRepay_blocksSupplyBorrow` | position + debt, then `setReserveFrozen(WETH,true)` | `withdraw` OK, `repay` OK; `supply` and `borrow` → `"MiniLend: frozen"` |
| T1-24 | `MiniLend.t.sol::test_paused_blocksAll` | `setReservePaused(WETH,true)` | supply, withdraw (including max), borrow, repay → `"MiniLend: paused"` |
| T1-25 | `MiniLend.t.sol::test_repay_clamps` | debt 100e18, borrower approved for 1000e18 | `repay(40e18)` → debt 60e18, liquidity +40e18; `repay(1000e18)` → only takes 60e18 (borrower balance −60e18 exactly), debt 0, event `Repaid(WETH,b,60e18)`; `repay` with no debt → no revert, `Repaid(WETH,b,0)`, nothing taken |
| T1-26 | `Scenario.t.sol::test_seedFeasible_noPriceTrick` | 2.2 prices **unchanged** (USDC 1e8, WETH/rsETH 2500e8). lend-eth: supply 2000e18 WETH + 3_000_000e6 USDC; bot collateral 900e18 rsETH + 4_500_000e6 USDC. lend-avax: supply 1000e18 WETH + 2_000_000e6 USDC; bot collateral 300e18 rsETH + 3_000_000e6 USDC | lend-eth: borrow 1200e18 WETH + 1_800_000e6 USDC **OK**; WETH `6000`, `165`/`325`; USDC `6000`, `availableLiquidity` 1_200_000e6 (USDC collateral not included); `totalCollateral` rsETH `900e18`, USDC `4_500_000e6`. lend-avax: borrow 550e18 WETH + 1_100_000e6 USDC **OK**; WETH `5500`, `143`/`306`. On each deployment, remaining margin $487,500 = 195 WETH: borrow 196e18 WETH → `"MiniLend: insufficient collateral"`, then 195e18 → OK (equality); then 1e18 → `"MiniLend: insufficient collateral"` (validates the 2.2 initial state for T2) |
| T1-27 | `Scenario.t.sol::test_drainWithoutReaction_matchesFixture` | lend-eth seed from T1-26 (without the margin borrows) + vault 150e18 within the 2000; `forgedRelease` 5000; collat; attacker borrows 100e18 per slice, 2 withdrawals of 100e18 by bots interleaved | final: `totalSupplied 1800e18`, `totalBorrowed 1800e18`, liquidity 0, `10000`, `6715`/`7900`, `totalCollateral` rsETH `5900e18`, `backingRatioBps 1935`; next slice → `"MiniLend: insufficient liquidity"`; `vault.emergencyWithdraw` returns `0`; `setReserveFrozen(rsETH,true)` → `frozen` |
| T1-28 | `Scenario.t.sol::test_guardianExitsBeforeDrain` | lend-eth seed from T1-26 (without the margin borrows) + vault positions 150e18 WETH and 400_000e6 USDC; `forgedRelease`; guardian `emergencyWithdraw` ×2; then drain | returns `150e18` and `400_000e6` (100% withdrawable); `weth.balanceOf(vault)==150e18`; a passive bot `withdraw(max)` after the drain → `0` |
| T1-29 | `TreasuryVault.t.sol::test_roles_and_supply` | | `owner()`, `guardian()`, `depositsPaused()==false`; guardian/alice `supply` → `"Vault: only owner"`; **vault balance**: owner holds 150e18 WETH, vault 0 → owner `supply(150e18)` reverts `ERC20InsufficientBalance`; mint 150e18 **to the vault** → owner supply 150e18 → vault position `150e18`, `weth.balanceOf(vault)==0`, owner balance **unchanged** (150e18), `Supplied(market,WETH,150e18)` |
| T1-30 | `TreasuryVault.t.sol::test_pause_unpause` | | guardian `pauseDeposits` → `true` + `DepositsPaused(guardian)`; 2nd call (guardian then owner) does not revert, state stays `true`, re-emits `DepositsPaused`; owner `supply` → `"Vault: deposits paused"`; guardian `unpauseDeposits` → `"Vault: only owner"`; alice `pauseDeposits` → `"Vault: only guardian or owner"`; owner unpause → `false` + `DepositsUnpaused(owner)` |
| T1-31 | `TreasuryVault.t.sol::test_emergencyWithdraw_toVaultOnly` | position 150e18, liquidity 800e18 | guardian → returns `150e18`, `weth.balanceOf(vault)==150e18`, guardian and owner `0`, event `EmergencyWithdrawal(market,WETH,150e18,guardian)`; liquidity 100e18 → `100e18`; liquidity 0 → returns `0` **without revert** + `EmergencyWithdrawal(market,WETH,0,guardian)`; asset with no vault position (USDC never deposited) → `0` without revert + event with amount 0; alice → `"Vault: only guardian or owner"`; guardian `withdraw` → `"Vault: only owner"` |
| T1-32 | `TreasuryVault.t.sol::test_emergencyWithdraw_states` | | works if `depositsPaused`; works if reserve frozen; reserve paused → revert `"MiniLend: paused"` (bubbled up as is, no `EmergencyWithdrawal` event, position intact: T4 marks the action `failed`) |
| T1-33 | `TreasuryVault.t.sol::test_setGuardian` | | alice → `"Vault: only owner"`; owner `setGuardian(bob)` → old guardian refused, bob accepted |
| T1-34 | `TreasuryVault.t.sol::testFuzz_guardianNeverLosesFunds(uint8[] ops)` | random sequence of guardian calls (pause, emergencyWithdraw USDC/WETH) | `balanceOf(vault) + position` constant for each asset; no token held by the guardian |
| T1-35 | `EvidenceRegistry.t.sol::test_anchor` | `vm.roll(123)` | `anchoredAt(h)==0` before; `anchor(h,"decision","s3://b/DEC-1.json")` → `anchoredAt(h)==123`, event `Anchored(h,"decision",uri,sender)`; 2nd anchoring → `"Evidence: already anchored"` |
| T1-36 | `Deploy.t.sol::test_deployAll_configuration` | `new Deploy().deployAll(roles anvil)` | prices 1e8/2500e8/2500e8; for each MiniLend: `protocolGuardian==pg`, `getAssets()==[USDC,WETH,rsETH]`, LTV 8000/8000/7500, borrowable true/true/false, nothing frozen; vault owner/guardian = index 1/2; `rseth.bridge()==bridge`, `bridge.weth()==WETH`; `totalSupply()==0` for the 3 tokens (T1 mints nothing) |
| T1-37 | `Deploy.t.sol::test_deployAll_addressesMatchFixtures` | same | the 9 addresses = those listed in 7 |
| T1-38 | `test_t1_deployment.py::test_t1_local_json_format` | skip if `deployments/local.json` missing | exact 2.3 keys, `network=="local"`, `chain_id==31337`, ids `["lend-eth","lend-avax"]`, exact labels, 3 bots, checksummed addresses |
| T1-39 | `test_t1_deployment.py::test_t1_addresses_have_code` | skip if RPC `127.0.0.1:8545` unreachable | `eth.get_code` non-empty for assets, contracts, lending; otherwise fails with "anvil restarted: rerun make deploy" |
| T1-40 | `test_t1_deployment.py::test_t1_abi_files` | | 7 files, each a `list`; `MiniLend` contains `getReservesData`, `withdraw`, `getUserSupplied`; `TreasuryVault` contains `emergencyWithdraw`, `pauseDeposits`; `EvidenceRegistry` contains `anchoredAt` |
| T1-41 | `test_t1_deployment.py::test_t1_onchain_config_and_roles` | same as T1-39 | via `chain.load_abi` + local Web3: oracle prices, `getAssets` order, LTV USDC/WETH 8000 and rsETH 7500, `vault.owner()==roles.owner`, `roles[r] == Account.from_key(settings.private_key(r)).address` for the 6 roles |
| T1-42 | `test_t1_deployment.py::test_t1_fuji_json_format` | skip if `deployments/fuji.json` missing; no network | `chain_id==43113`, `explorer=="https://testnet.snowtrace.io"`, no `"0x…"` value, `deployments/fuji.md` exists |
| T1-43 | `test_t1_deployment.py::test_t1_fund_roles_refuses_local` | no network | `subprocess.run(["python3","contracts/script/fund_roles.py","--amount","0.5"], env={…, "NETWORK":"local"})` → code ≠ 0, message contains `local`; no transaction sent |
| T1-44 | `test_t1_deployment.py::test_t1_deploy_fuji_requires_force` | skip if `deployments/fuji.json` missing; no network (`RPC_URL` empty) | `bash contracts/script/deploy.sh` with `NETWORK=fuji`, `FORCE` absent → code ≠ 0, message contains `FORCE=1`; `deployments/fuji.json` unchanged (same sha256) and no new file in `deployments/history/` |

#### Definition of done

- [ ] `forge build` with no blocking warning; `forge test`: T1-01 to T1-37 green; `forge coverage` > 90% of `src/` lines (indicative).
- [ ] The 7 `abi/*.json` committed (raw lists) and up to date (`make abi` produces no diff).
- [ ] `make chain` then `make deploy` on fresh anvil → valid `deployments/local.json`, addresses = fixtures; `pytest backend/tests/test_t1_deployment.py` green (T1-38 to T1-41, T1-43).
- [ ] `make deploy` rerun on the same anvil works (new addresses, `local.json` rewritten).
- [ ] `make fund-roles AMOUNT=0.5` run on Fuji: the 8 roles (excluding deployer) have ≥ 0.5 AVAX.
- [ ] Fuji deployment done, `deployments/fuji.json` + `fuji.md` + `history/` committed, T1-42 and T1-44 green, `make deploy` on Fuji refused without `FORCE=1`, Snowtrace links opened and checked by hand.
- [ ] No key in the repo or in logs (`git grep -i "PK="` empty outside `.env.example`, `make deploy` output reviewed).
- [ ] The team is notified (Fuji addresses, ABIs, `make fund-roles` available; T2 knows the 2.2 initial state is feasible as is, validated by T1-26).

#### Known pitfalls

1. **`vm.writeJson` runs during simulation**, before the transactions are sent: if the broadcast fails, the file contains addresses with no code. Hence `.pending.json` + promotion after the `eth_getCode` check.
2. **Collateral ≠ liquidity**: the bots borrow against 900 rsETH + 4.5 M USDC (`lend-eth`, capacity $5,287,500 for $4.8 M) and 300 rsETH + 3 M USDC (`lend-avax`, $2,962,500 for $2.475 M). If `depositCollateral` added USDC collateral to `totalSupplied`, the 2.2 rates and liquidity would be wrong (and the attacker could borrow the bots' collateral). Two separate balances, accounting liquidity, and **no oracle price change** at seed time (validated by T1-26). If you forget LTV 8000 on USDC/WETH at listing, the seed reverts `"insufficient collateral"`.
3. **Nonces and addresses**: any deployer call (e.g. `setPriceE8`) before the 9 deployments are done shifts all addresses; and a `make deploy` on an already-used anvil gives different addresses (normal; `chain.load_deployment()` rereads the file).
4. **Fixtures rounded as float**: the last line of `snapshots_attack.jsonl` shows `6714`/`7899` at U = 100%; the contract returns `6715`/`7900` (integers, 2.2 value). Warn T3: do not compare on-chain rates to the fixtures to the unit.
5. **Empty keys in `.env`** (`DEPLOYER_PK=` copied from `.env.example`): `vm.envOr` returns `""`, treat it as absent; `vm.envUint` on `""` crashes. Key without `0x`: prefix it before `vm.parseUint`.
6. **Local with Fuji keys in `.env`**: `settings.private_key` uses them locally too; those accounts have no anvil ETH → "insufficient funds". Comment out the `*_PK` lines to work locally.
7. OZ v5: `Ownable` requires `Ownable(initialOwner)` and errors are custom errors (`expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice))`).
8. Missing `fs_permissions` → "path not allowed"; `--slow` forgotten on Fuji → in-flight nonces and RPC timeouts; public RPC → HTTP 429.
9. `anvil` loses its state when stopped: after each `make chain`, redo `make deploy` then `make seed`.
10. `forge inspect … abi` prints a table in recent versions: export from `out/` (script provided).

#### Later (phase 2)

- Accrued interest (index), liquidations, collateral withdrawal, exposed health factor: would allow cascading liquidation scenarios.
- Market allowlist in `TreasuryVault` (the guardian can only call `emergencyWithdraw` on approved markets); real Safe module instead of the simplified vault.
- Oracle with `updatedAt` and freshness check; mint caps on the bridge.
- `EvidenceRegistry` with a list of authorised issuers and `kind` validation.
- `anvil --dump-state/--load-state` for a reusable seeded state; automated source verification in the Fuji deployment.

#### Claude Code starter prompt

```
You are working on task T1 (on-chain contracts) from the TASKS.md file at the repo root.
1. Read sections 1 and 2 of TASKS.md (2.2 and 2.3 are the exact contract), then the whole T1 section.
   Also read backend/settings.py, backend/chain.py and fixtures/deployments.example.json (addresses only).
2. Modify ONLY: contracts/**, deployments/**, abi/**, mk/t1.mk, backend/tests/test_t1_deployment.py.
   Any change needed elsewhere or in section 2: do not edit, write the request in
   docs/contract-requests.md (what, why, who is impacted) and tell me.
3. No key in the repo or in logs; locally, use the anvil accounts (public mnemonic).
4. Work order: (a) Foundry project + exact 2.2 interfaces that compile, ABI export,
   Deploy.s.sol + local make deploy, to unblock the team; (b) write tests T1-01 to T1-44
   BEFORE the full implementation, then implement until make test-t1 is green;
   (c) Fuji deployment (only when I ask you, with my keys in .env):
   make fund-roles AMOUNT=0.5 then make deploy (FORCE=1 only if I confirm).
5. Revert messages, event names, ReserveData field order, deployment order
   (addresses = fixtures on fresh anvil): follow them to the letter.
6. Before each commit: make test-t1 green; push often after each green test.
```


---
### T2 · Scenario: seed, attack, normal traffic, reset

**Goal.** Provide the scripts that put the chain (anvil or Fuji) into the starting state of 2.2 (`seed`), replay the attack of 1.2 reproducibly (`attack`), produce benign traffic (`normal`) and reset everything (`reset`). Each run writes its **ground truth** (`RunRecord`) for evaluation (T7), and the `/api/demo/*` API lets the dashboard (T6) launch attack and reset.

**Depends on.**
- T1 → contracts + `make deploy` + `deployments/<network>.json` + `abi/*.json` → meanwhile: pure tests only (params, planner, RunRecord, API with fake runner); chain tests skip themselves.
- T0 → 2.4 helpers in `backend/chain.py` → if `token()`, `vault()`, `bridge()`, `oracle()`, `bot_accounts()` are not there yet (today only `w3`, `load_deployment`, `load_abi`, `contract`, `lending`, `account`, `send`, `explorer_tx` exist), use the temporary shim `scenario/_compat.py` (step 1), to delete when T0 delivers.
- T0 → `backend/store.py` (`store.reset()`, which increments `store.generation`) → call isolated in `_reset_store()` of `backend/api/demo.py`, replaced by a counter in tests.
- T1 → `make fund-roles` (sends test AVAX to the roles on Fuji) → on `local`, nothing to do (anvil accounts already funded).
- T3 → honour the maintenance mode of 2.10 (the engine evaluates no rule while `data/runtime/<network>/maintenance.flag` exists) → T2 creates and deletes the file no matter what; the scripts run with the engine off (`ENGINE_ENABLED=false`) or on. T4: no dependency.

**Unblocks.** T7 (runs `python -m scenario.attack/normal --json`, reads `data/runs/*.json`), T6 ("Run attack" / "Reset" buttons via `/api/demo/*`), T3/T4/T5 (real chain state matching 2.2 for integration), T0 (`make demo` calls `make seed`), T9 (demo script).

**Owned files.**
- `scenario/common.py`, `scenario/params.py`, `scenario/seed.py`, `scenario/attack.py`, `scenario/normal.py`, `scenario/reset.py`, `scenario/testing.py`, `scenario/_compat.py` (temporary)
- `backend/api/demo.py`
- `mk/t2.mk`
- `backend/tests/test_t2_params.py`, `test_t2_common.py`, `test_t2_normal_plan.py`, `test_t2_demo_api.py`, `test_t2_seed_chain.py`, `test_t2_attack_chain.py`, `test_t2_normal_chain.py`
- Generated (not committed): `data/runs/<run_id>.json`, `data/runtime/<network>/maintenance.flag` (temporary, during seed and reset)
- Not T2's: `scenario/__init__.py` (T0, already created), `README.md` (T9: provide your paragraph in the PR)

**Read before starting.** TASKS.md 1.2 (phases), 1.5, 2.1 (roles, anvil keys), 2.2 (interfaces + parameter table), 2.3, 2.4, 2.5 (identifiers), 2.9 (demo routes, error codes, `seed` semantics), 2.10 (maintenance mode), 2.11. Files: `backend/models.py` (`DemoRun`, `RunRecord`), `backend/settings.py`, `backend/chain.py`, `fixtures/run_record.example.json`, `fixtures/demo_run.json`. **Do not read** `backend/config/rules.yaml` or 2.7 to tune the attack (non-circularity, see Pitfalls).

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Deployed addresses | `deployments/<network>.json` (2.3) | T1 (`make deploy`) | none: chain tests skip; for the loading code, `fixtures/deployments.example.json` |
| ABIs | `abi/<Contrat>.json` (raw ABI list) | T1 (`make abi`) | same |
| Role keys | `settings.private_key(role)`, `settings.bot_pks()` | T0 | on `local`: anvil accounts (deployer 0, owner 1, guardian 2, protocol_guardian 3, attacker 4, bots 6/7/8) |
| web3 helpers | `backend.chain` (2.4) | T0 | `scenario/_compat.py` |
| Models | `RunRecord`, `DemoRun` (`backend/models.py`) | T0 | already delivered |
| `store.reset()` | `backend.store.store` | T0 | function patched in tests |
| `make deploy FORCE=1` | shell command, exit code 0 | T1 | `deploy_cmd=["true"]` injected in `reset` tests |
| Test AVAX for roles (fuji) | `make fund-roles` | T1 | not needed on `local` |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| Chain state after seed | exactly table 2.2 (details in 3.2) | T3, T4, T5, T7, demo |
| `data/runs/<run_id>.json` | serialised `RunRecord` (`model_dump_json(indent=2)`), one file per attack run (label `attack`) and normal run (label `normal`) | T7 |
| `data/runtime/<network>/maintenance.flag` | file present during all of `seed` and all of `reset`, deleted in a `finally` (2.10) | T3 (engine) |
| `--json` lines on stdout | one JSON line per step: `{"run_id","step","status","block","tx_hash","msg","at"}` | `backend/api/demo.py`, T7 |
| `POST /api/demo/attack`, `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` | `DemoRun` (2.9) | T6 |
| Python functions | `run_seed()`, `run_attack()`, `run_normal()`, `run_reset()`, `attack_params()`, `normal_params()` | T7 (direct import possible) |
| make targets | `seed`, `attack SEED= VARIANT=`, `normal MINUTES= SEED=`, `reset`, `test-t2` | everyone |

#### Detailed specification

**1. Foundation (`scenario/common.py`, `scenario/_compat.py`, `scenario/testing.py`)**

```python
# _compat.py (temporary): only via chain.contract() and chain.load_deployment()
def token(symbol: str) -> Contract      # ABI "RsETH" if symbol == "rsETH", else "MockERC20"; address = dep["assets"][symbol]
def vault() / bridge() / oracle()       # contract("TreasuryVault") / contract("MockBridge") / contract("MockOracle")
def bot_accounts() -> list[LocalAccount] # [Account.from_key(k) for k in settings.bot_pks()]
# common.py
class ScenarioError(Exception): ...   # exit 1
class PreflightError(Exception): ...  # exit 2
def units(amount: int | str | Decimal, symbol: str) -> int     # USDC 6 decimals, WETH/rsETH 18; units(150,"WETH") == 150 * 10**18
def new_run_id(kind: str, seed: int, now: datetime | None = None) -> str   # "RUN-20261011080000-attack-42" (UTC)
def reserve(deployment_id: str, symbol: str, block: int | str = "latest") -> dict
    # getReservesData() indexed by getAssets(); snake_case keys: total_supplied, total_borrowed, available_liquidity,
    # utilization_bps, total_collateral, ltv_bps, frozen, paused (ints / bools)
def tx(fn, sender, step: str, emit: "Emitter", expect_revert: bool = False) -> dict | None
    # calls chain.send; status 0 -> ScenarioError; ContractLogicError (raised by estimate_gas) -> ScenarioError,
    # except expect_revert=True: emits status "blocked" and returns None
def ensure_allowance(acct, symbol: str, spender: str) -> None   # approve(2**256-1) only if allowance < 2**255
def write_run_record(rec: RunRecord) -> Path   # settings.DATA_DIR/"runs"/f"{rec.run_id}.json", write .tmp then os.replace
def maintenance_flag_path() -> Path            # settings.DATA_DIR/"runtime"/settings.NETWORK/"maintenance.flag"
@contextmanager
def maintenance(emit: "Emitter") -> Iterator[None]
    # creates the folder and the file (content: run_id + ISO date) on entry, emits "maintenance_on" (info);
    # deletes the file in a finally (missing_ok=True), emits "maintenance_off" (info), even if an exception propagates
class Emitter:
    def __init__(self, run_id: str, json_mode: bool, stream=sys.stdout)
    def __call__(self, step: str, msg: str, status: str = "ok", block: int | None = None, tx_hash: str | None = None) -> None
    # json_mode: print(json.dumps({...}), flush=True); otherwise "[step] msg (block=…, tx=…)"
```
`status ∈ {"ok", "info", "blocked", "failed"}`. Always `flush=True` (otherwise the API sees nothing before the end).
`testing.py`: `local_chain_ready() -> bool` (true if `settings.NETWORK == "local"`, `w3().is_connected()`, `chain_id == 31337` and `deployments/local.json` exists), `evm_snapshot() -> str`, `evm_revert(snap_id: str) -> None` via `w3().provider.make_request("evm_snapshot", [])`.

**2. Parameters (`scenario/params.py`, pure, no chain access)**

```python
@dataclass(frozen=True)
class AttackParams:
    variant: str; seed: int; market: str          # "lend-eth"
    forged_amount: int                            # rsETH, human units
    drain_asset: str                              # "WETH" | "USDC"
    chunk: int                                    # human units of drain_asset
    interval_s: float; warmup_s: float; gap_s: float; freeze_delay_s: float; cooldown_s: float
    withdraw_after: tuple[int, ...]               # indexes (1-based) of the borrows after which a bot withdraws
    bot_withdraw_amount: int; max_chunks: int = 200
    def as_params(self) -> dict[str, str | int | float | bool]
    # mandatory keys (contract names): forged_amount, chunk_weth (= chunk if WETH, else 0), interval_s,
    # bot_withdrawals (= len(withdraw_after)); extra keys: drain_asset, chunk_usdc (= chunk if USDC, else 0),
    # withdraw_after -> "4,5" (no list in RunRecord.params), bot_withdraw_amount
def attack_params(variant: str = "default", seed: int = 0, network: str = settings.NETWORK) -> AttackParams
def normal_params(minutes: float, seed: int = 0, network: str = settings.NETWORK, ticks: int | None = None) -> NormalParams
```

| Parameter | `default` | `slow` | `usdc` | Draw if `seed ≥ 1` (`random.Random(seed)` only) |
|---|---|---|---|---|
| `forged_amount` | 5,000 | 5,000 | 5,000 | multiple of 500 in [3,000; 8,000] |
| `drain_asset`, `chunk` | WETH, 100 | WETH, 25 | USDC, 250,000 | WETH: {50, 100, 150, 200}; USDC: {100,000, 250,000, 400,000}; `slow`: {10, 25, 40} |
| `interval_s` | 8 (fuji) / 1 (local) | ×3 | same as default | × uniform [0.75; 1.25], rounded to 0.1 |
| `warmup_s` / `gap_s` | 3 × interval / 1 × interval | same | same | same (derived) |
| `withdraw_after`, `bot_withdraw_amount` | (4, 5), 100 WETH | (12, 20), 100 WETH | (2, 3), 250,000 USDC | 1 to 3 distinct indexes in [2; 7]; amount = 1 × chunk WETH rounded to 100, or 250,000 USDC |
| `freeze_delay_s` / `cooldown_s` | 10 × interval / 1 × interval | same | same | same |

`seed = 0` (or `--seed` absent) = exact default params, no draw. `seed ≥ 1` = deterministic draw. Drawing a random seed (API case `seed = null`, 2.9) is done by `backend/api/demo.py`, never here. Allowed variants: `default`, `slow`, `usdc`; unknown variant → `ValueError`. With default params: 6 chunks of 100 WETH and 2 bot withdrawals of 100 WETH (identical to `fixtures/snapshots_attack.jsonl`). CLI: `--interval-s`, `--warmup-s`, `--freeze-delay-s` override after the draw (used by tests).

**3. Seed (`scenario/seed.py`)**

3.1 Targets (constant `SEED_TARGET`, human units): fixed bot roles: `bots[0]` = lender, `bots[1]` = historical borrower, `bots[2]` = active borrower of normal traffic.

| Who | Action | lend-eth | lend-avax |
|---|---|---|---|
| deployer | `mint` | bots[0]: 3,250 WETH + 5,300,000 USDC; bots[1]: 1,200 WETH + 7,500,000 USDC; bots[2]: 500 WETH; vault (vault address): 250 WETH + 700,000 USDC | |
| bots[0] | `supply` | 1,850 WETH, 2,600,000 USDC | 900 WETH, 1,700,000 USDC |
| bots[1] | `bridge.deposit(1200)` then `depositCollateral(rsETH)` | 900 rsETH | 300 rsETH |
| bots[1] | `depositCollateral(USDC)` | 4,500,000 USDC | 3,000,000 USDC |
| bots[1] | `borrow` | 1,200 WETH, 1,800,000 USDC | 550 WETH, 1,100,000 USDC |
| owner | `vault.supply(market, asset, amount)` | 150 WETH, 400,000 USDC | 100 WETH, 300,000 USDC |

Expected result (= 2.2): lend-eth WETH 2,000 / 1,200 (6,000 bps), USDC 3,000,000 / 1,800,000; lend-avax WETH 1,000 / 550 (5,500 bps), USDC 2,000,000 / 1,100,000; rsETH `totalSupply` 1,200, `totalBacking` 1,200, `backingRatioBps` 10,000; rsETH collateral 900 / 300 and USDC collateral 4,500,000 / 3,000,000 (`total_collateral` of the USDC reserve, **separate** from `total_supplied`: it does not increase borrowable liquidity); vault `idle_balances` at 0, `depositsPaused == false`. The vault mints go **to the vault address**: `TreasuryVault.supply` uses the vault's own balance (2.2), no `transferFrom` or `approve` on the owner side.

3.2 **Covering the borrows without touching prices.** With the prices of 2.2 (USDC $1, WETH $2,500, rsETH $2,500), bots[1]'s capacity comes from rsETH (LTV 7500) **and** USDC collateral (LTV 8000): lend-eth 900 × 2,500 × 0.75 + 4,500,000 × 0.8 = $5,287,500 for $4,800,000 borrowed; lend-avax 300 × 2,500 × 0.75 + 3,000,000 × 0.8 = $2,962,500 for $2,475,000. So the USDC collateral must be deposited **before** the `borrow` calls. Prices never change: no step of the seed (nor of the attack, nor of normal traffic) calls `setPriceE8`.

3.3 **Maintenance mode during the seed (2.10).** The seed borrows make liquidity drop and utilisation rise: with the engine on, this would look like an attack. So all of `run_seed()` runs inside `with maintenance(emit):` (file `data/runtime/<network>/maintenance.flag` created at the start, deleted in a `finally`, even on failure). The engine (T3) keeps storing snapshots but evaluates no rule and clears its window when the file disappears. The vault guardian is never touched (`setGuardian` is not called).

3.4 Order: preflight → `maintenance` opened → mints → `ensure_allowance` for every (bot, token, spender) pair used by seed **and** normal (bots[0] USDC/WETH → 2 markets; bots[1] USDC → 2 markets for collateral; bots[1] and bots[2] WETH → bridge, rsETH → 2 markets, WETH/USDC → 2 markets for `repay`) → bots[0] supplies → bridge + rsETH collateral → USDC collateral → borrows → vault supplies → check `detect_seed_state() == "seeded"` → `maintenance` closed (finally).

3.5 Idempotence: `detect_seed_state() -> Literal["empty", "seeded", "partial"]`. `empty`: rsETH supply 0 and all `total_supplied`/`total_collateral` at 0. `seeded`: all values of 3.1 exact (including USDC collaterals) + guardian = `roles.guardian` + USDC/WETH/rsETH prices = $1 / $2,500 / $2,500. Otherwise `partial`. `run_seed()`: `seeded` → emits `already_seeded`, sends **no** transaction, returns `{"status": "already_seeded"}`; `partial` → `PreflightError("partial seed state, run make reset")`, exit 2; `empty` → full seed, returns `{"status": "seeded", "txs": n, "end_block": b}`.

3.6 Preflight (exit 2): deployment file missing, `chain_id` ≠ `settings.CHAIN_ID`, fewer than 3 bots, on fuji native balance < 0.05 AVAX for a role in use (message listing the affected addresses and asking to run T1's `make fund-roles`). `run_seed(manage_maintenance: bool = True)`: `reset` calls it with `False` because it has already opened maintenance mode (otherwise the seed's `finally` would delete the file before the reset ends).

**4. Attack (`scenario/attack.py`)**

```python
def run_attack(p: AttackParams, run_id: str, emit: Emitter) -> RunRecord
def main(argv: list[str] | None = None) -> int
# CLI: python -m scenario.attack [--seed N] [--variant default|slow|usdc] [--json] [--run-id RUN-…]
#       [--interval-s X] [--warmup-s X] [--freeze-delay-s X]
```
Algorithm (M = `p.market`, A = `p.drain_asset`, X = attacker, B0 = `bots[0]`):
1. Preflight: `detect_seed_state()` must be `seeded` (otherwise exit 2, unless `--skip-seed-check`). `start_block = w3().eth.block_number`. `treasury_supplied_at_start` = `getUserSupplied(vault, asset)` for each deployment × {USDC, WETH}, key `"<deployment>:<asset>"`, as a base-units string: **always the 4 keys** `lend-eth:WETH`, `lend-eth:USDC`, `lend-avax:WETH`, `lend-avax:USDC` (value `"0"` if the position is empty).
2. `sleep(warmup_s)` (monitor baseline), emits `start`.
3. `forgedRelease(X, units(forged_amount, "rsETH"))` sent by X → `phase_blocks["forged_mint"]` = `attack_start_block`. Emits `forged_mint` with the `backingRatioBps` read right after (1935 by default).
4. `sleep(gap_s)`; `ensure_allowance(X, "rsETH", M)`; `depositCollateral(rsETH, amount)` → `collateral_deposit` (block of the deposit, not of the approve).
5. `sleep(gap_s / 2)` then loop, `i = 1..max_chunks`: read `available_liquidity` of A on M **every iteration** (the vault may have withdrawn in between); if 0 → exit; `amount = min(units(chunk), avail)`; `borrow(A, amount)` by X; the first sets `first_borrow`; if liquidity read afterwards is 0 → `liquidity_zero` = block of this borrow, exit. If `i ∈ withdraw_after`: B0 `withdraw(A, bot_withdraw_amount, B0)` with `expect_revert=True` (if liquidity is insufficient: step `bot_withdraw` status `blocked`, that is the stuck supplier). `sleep(interval_s)` between iterations. Revert "insufficient collateral" → step `failed`, exit loop, `liquidity_zero` absent, exit 1 after writing the record.
6. Final rush: one B0 attempt `withdraw(A, bot_withdraw_amount)` → expected `blocked`.
7. `sleep(freeze_delay_s)`; protocol_guardian `setReserveFrozen(rsETH, true)` on M → `protocol_freeze`.
8. `sleep(cooldown_s)`; `end_block`; `RunRecord(label="attack", network=settings.NETWORK, variant, seed, params=p.as_params(), …)` → `write_run_record`; emits `done` with `msg` = file path.

Expected values, default, no vault reaction (identical to `fixtures/snapshots_attack.jsonl`): 6 successful borrows (600 WETH), 2 successful bot withdrawals (after borrows 4 and 5), liquidity 800 → 0; lend-eth WETH `total_supplied` 1,800, `total_borrowed` 1,800, 10,000 bps; lend-eth rsETH collateral 5,900; rsETH supply 6,200, backing 1,935 bps; rsETH frozen on lend-eth only; lend-avax untouched. Never assume "8 chunks": if a fixture still shows `chunks: 8`, it is stale (report it to T0); the params written are those of `as_params()` (`forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals`…).

**5. Normal traffic (`scenario/normal.py`)**

```python
@dataclass
class MarketView:    # per (deployment, asset): supplied, borrowed, available (int base units)
class NormalAction:  kind: Literal["supply","withdraw","borrow","repay","large_deposit","bridge_deposit"]; actor: int; deployment_id: str; asset: str; amount: int
def plan_next_action(view: dict, rng: random.Random, p: NormalParams, tick: int) -> NormalAction | None   # PURE
def run_normal(p: NormalParams, run_id: str, emit: Emitter) -> RunRecord
# CLI: python -m scenario.normal --minutes M [--seed N] [--json] [--run-id …] [--tick-s X] [--ticks N]
```
- `tick_s` = 6 (fuji) / 1 (local); number of ticks = `ticks` or `int(minutes*60/tick_s)`.
- Tick 0: `bridge_deposit` bots[2] `bridge.deposit(200 WETH)` then 150 rsETH collateral on lend-eth, 50 on lend-avax (backing stays 10,000). Tick `int(0.4 × N)`: `large_deposit` bots[0] `supply` 300 WETH on lend-eth.
- Other ticks, weighted draw: supply 30 (bots[0], WETH [5; 40] or USDC [10,000; 100,000]), withdraw 25 (bots[0]), borrow 25 (bots[2]), repay 20 (bots[2]); market drawn among the 2 deployments, asset among USDC/WETH.
- Guards (action skipped with a `skip` step if impossible): amount ≤ 10% of `available`; after a borrow `(borrowed+amt)*10000/supplied ≤ 8500`; after a withdraw `borrowed*10000/(supplied-amt) ≤ 8500` and `amt ≤` bot's position; borrow ≤ 80% of bots[2]'s remaining capacity (collateral × oracle price × LTV − debts); repay ≤ min(debt, balance).
- Forbidden: `forgedRelease`, `setReserveFrozen/Paused`, `setPriceE8`, any vault operation, any borrow by bots[1] (its remaining capacity is reserved for the 2.2 state).
- `run_normal` is **blocking** (returns at the end of the ticks; so does `make normal`) and always writes a `RunRecord(label="normal", variant="default", attack_start_block=None, phase_blocks={}, treasury_supplied_at_start=<the 4 keys>)` via `write_run_record`, even when interrupted by Ctrl-C (in a `finally`, `end_block` = last block read).

**6. Reset (`scenario/reset.py`)**: `run_reset(emit, deploy_cmd=("make", "deploy", "FORCE=1")) -> None`. The whole reset runs inside `with maintenance(emit):` (file created at the start, deleted in a `finally`). Runs `deploy_cmd` (cwd = `settings.ROOT`, current env, which already contains `NETWORK`; never redefine it), relays each line as a `deploy` step (status `info`), exit ≠ 0 → `ScenarioError` (exit 1). `FORCE=1` is mandatory on fuji (T1 refuses to overwrite `deployments/fuji.json` without it) and has no effect on local. Checks that `deployments/<network>.json` changed (mtime or `deployed_at_block`). Then `run_seed(manage_maintenance=False)` (exit 2 on failure). On fuji, warning: redeploy costs gas, ~2 min, addresses change. No RunRecord for reset/seed.

**7. API (`backend/api/demo.py`)**

```python
class AttackBody(BaseModel): seed: Optional[int] = None; variant: Literal["default", "slow", "usdc"] = "default"
class Runner(Protocol):
    def start(self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]) -> None
class SubprocessRunner:   # Popen(argv, cwd=ROOT, stdout=PIPE, stderr=STDOUT, text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"}) + reader thread
def get_runner() -> Runner          # FastAPI dependency, overridden in tests
def _reset_store() -> None          # from backend.store import store; store.reset()
_RUNS: dict[str, DemoRun]; _LOCK = threading.Lock()
```
- `USE_FIXTURES=true` → current fixture behaviour (2.9). Otherwise:
- `POST /api/demo/attack`: semantics of 2.9: `seed = null` (or absent) → the backend draws `seed = random.SystemRandom().randint(1, 999999)` and returns it; `seed = 0` → default params, no randomness; `seed ≥ 1` → as is; `seed < 0` → 422. `run_id = new_run_id("attack", seed)`; argv `[sys.executable, "-m", "scenario.attack", "--json", "--run-id", run_id, "--variant", v, "--seed", str(seed)]`; `DemoRun(kind="attack", variant=v, seed=seed, status="running", params=attack_params(v, seed).as_params())` stored then returned immediately (the front shows the seed so the run can be replayed).
- `POST /api/demo/reset`: argv `python -m scenario.reset --json --run-id …`; on exit 0: `_reset_store()` **then** `status="done"`; exit ≠ 0: no store reset, `status="failed"`.
- `on_line`: JSON line → `f"[{block}] {step}: {msg}"` (without `[block]` if null); non-JSON line → as is; 500 lines max (keep the latest).
- `on_exit(code)`: `finished_at = now(UTC)`, `done` if 0, else `failed` + line `"exit code {code}"`.
- Only one `attack`/`reset` run at a time: otherwise `409 {"detail": "demo run already running: RUN-…"}` (code defined by 2.9). `variant` outside `default|slow|usdc` or invalid body → 422 (FastAPI validation).
- `GET /api/demo/runs/{run_id}`: `DemoRun` or `404 {"detail": "run not found"}`.

**8. `mk/t2.mk`**
```make
# NETWORK is NEVER defined here: the Python scripts read it from .env, and the command line wins (NETWORK=local make seed).
PYTHON ?= python3
SEED ?= 0
VARIANT ?= default
MINUTES ?= 5
.PHONY: seed attack normal reset test-t2
seed:    ; $(PYTHON) -m scenario.seed
attack:  ; $(PYTHON) -m scenario.attack --seed $(SEED) --variant $(VARIANT)
normal:  ; $(PYTHON) -m scenario.normal --minutes $(MINUTES) --seed $(SEED)   # blocking, writes a RunRecord label "normal"
reset:   ; $(PYTHON) -m scenario.reset                                         # make deploy FORCE=1 then seed, under maintenance.flag
test-t2: ; $(PYTHON) -m pytest backend/tests/test_t2_*.py -q
```
`make test` (T0) calls `test-t2`; never filter with `-k`.

#### Tests that must pass

Single command: `make test-t2`. The `*_chain.py` files start with `pytestmark = pytest.mark.skipif(not local_chain_ready(), reason="anvil + make deploy required")`. Chain setup: terminal 1 `anvil` (automine, faster) or `make chain`; terminal 2 `NETWORK=local make deploy`. Session fixture: `run_seed()` once then `evm_snapshot()`; each test starts with `evm_revert` + a new `evm_snapshot`. Test attacks pass `interval_s=0, warmup_s=0, freeze_delay_s=0`.

| Id | Type | File :: test | Setup | Expected result |
|---|---|---|---|---|
| T2-01 | unit | `test_t2_params.py::test_default_attack_params` | `attack_params("default", 0, "fuji")` | forged 5000, WETH, chunk 100, interval 8.0, warmup 24.0, freeze_delay 80.0, withdraw_after (4,5), bot 100; `network="local"` → interval 1.0 |
| T2-02 | unit | `::test_seeded_params_deterministic_and_in_range` | seeds 1..200, each variant | same seed → same params; forged ∈ [3000; 8000] multiple of 500; chunk in the set; 1–3 distinct indexes in [2; 7] |
| T2-03 | unit | `::test_variants` | `slow`, `usdc`, `"foo"` | slow chunk 25 interval 24.0; usdc USDC 250000; `"foo"` → `ValueError` |
| T2-04 | unit | `::test_as_params_types` | default, fuji network | all values str/int/float/bool; keys `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals` present; `forged_amount == 5000`, `chunk_weth == 100`, `interval_s == 8.0`, `bot_withdrawals == 2`, `withdraw_after == "4,5"`; variant `usdc` → `chunk_weth == 0`, `chunk_usdc == 250000` |
| T2-05 | unit | `::test_no_rules_coupling` | read `scenario/*.py` | none contains `rules.yaml`, `backend.rules`, `backend.engine`, `backend.config` |
| T2-06 | unit | `test_t2_common.py::test_run_id_format` | `new_run_id("attack", 42, datetime(2026,10,11,8,0,0,tzinfo=UTC))` | `"RUN-20261011080000-attack-42"` |
| T2-07 | unit | `::test_write_run_record_roundtrip` | `monkeypatch` `settings.DATA_DIR` → `tmp_path`; record = `fixtures/run_record.example.json` | file `tmp_path/runs/RUN-20261011080000-attack-42.json`; read back via `RunRecord.model_validate_json` == original |
| T2-08 | unit | `::test_emitter_json_line` | `Emitter(json_mode=True, stream=io.StringIO())` | one line, valid JSON, exactly the 7 keys of the Outputs section |
| T2-09 | unit | `::test_units` | — | `units(150,"WETH") == 150*10**18`; `units(400000,"USDC") == 400000*10**6` |
| T2-12 | unit | `::test_maintenance_flag_lifecycle` | `monkeypatch` `settings.DATA_DIR` → `tmp_path`; `with maintenance(emit): raise RuntimeError` | inside the block, `tmp_path/runtime/<network>/maintenance.flag` exists; after the exception, it no longer exists |
| T2-13 | unit | `::test_reset_runs_under_maintenance` | `run_reset(emit, deploy_cmd=["true"])` with `run_seed` patched (records flag existence and `manage_maintenance`) and the deployment file touched | flag present during `run_seed`, `manage_maintenance is False`, flag absent at the end; failing `deploy_cmd` → `ScenarioError` and flag absent |
| T2-10 | unit | `test_t2_normal_plan.py::test_guards_hold_over_2000_steps` | initial view 2.2, `rng=Random(7)`, apply each action to the view | utilisation ≤ 8500 everywhere; amount ≤ 10% of available; no `kind` outside the list |
| T2-11 | unit | `::test_scheduled_actions` | N = 50 ticks | tick 0 → `bridge_deposit`; tick 20 → `large_deposit` 300 WETH lend-eth |
| T2-20 | chain | `test_t2_seed_chain.py::test_seed_matches_contract_table` | session seed | the 4 lending reserves exactly as in 3.1; rsETH collaterals 900e18 / 300e18 and USDC 4500000e6 / 3000000e6 (`total_collateral`), USDC `total_supplied` unchanged by collateral; rsETH supply 1200e18, backing 10000; vault positions 150e18 / 400000e6 / 100e18 / 300000e6; idle 0 |
| T2-21 | chain | `::test_seed_leaves_prices_guardian_and_flag` | same | `getPriceE8` = 1e8 (USDC), 2500e8 (WETH), 2500e8 (rsETH); no `PriceUpdated` event after `deployed_at_block`; `vault.guardian() == roles.guardian`; `depositsPaused() is False`; `maintenance.flag` absent |
| T2-22 | chain | `::test_seed_idempotent` | rerun `run_seed()` | `{"status": "already_seeded"}`; nonces of all roles unchanged |
| T2-23 | chain | `::test_partial_state_rejected` | bots[0] `supply` 1 extra WETH | `detect_seed_state() == "partial"`; `run_seed()` raises `PreflightError` |
| T2-24 | chain | `::test_bot_balances` | same as T2-20 | bots[0] 500 WETH + 1,000,000 USDC; bots[1] 1,750 WETH + 2,900,000 USDC, 0 rsETH; bots[2] 500 WETH |
| T2-30 | chain | `test_t2_attack_chain.py::test_default_attack_end_state` | `run_attack(default)` | `backingRatioBps() == 1935`; lend-eth WETH available 0, supplied 1800e18, borrowed 1800e18, util 10000; attacker 600e18 WETH borrowed and in balance; rsETH collateral 5900e18; rsETH frozen lend-eth, not lend-avax; lend-avax WETH available 450e18 |
| T2-31 | chain | `::test_attack_run_record` | same | `data/runs/<run_id>.json` exists; label attack, variant default, seed 0; 5 phase keys; `forged_mint < collateral_deposit < first_borrow < liquidity_zero < protocol_freeze`; `attack_start_block == forged_mint`; `start_block < forged_mint`; `end_block ≥ protocol_freeze`; `treasury_supplied_at_start` = exactly the 4 keys `lend-eth:WETH` `"150000000000000000000"`, `lend-eth:USDC` `"400000000000"`, `lend-avax:WETH` `"100000000000000000000"`, `lend-avax:USDC` `"300000000000"`; `params` contains `forged_amount`, `chunk_weth`, `interval_s`, `bot_withdrawals` |
| T2-32 | chain | `::test_attack_json_cli` | `subprocess.run([sys.executable,"-m","scenario.attack","--json","--interval-s","0","--warmup-s","0","--freeze-delay-s","0"])` | exit 0; every line is JSON; counts: `borrow` 6, `bot_withdraw` 2 `ok`, 1 `blocked`, then `liquidity_zero`, `protocol_freeze`, `done` |
| T2-33 | chain | `::test_attack_after_treasury_exit` | owner `vault.emergencyWithdraw(lend-eth, WETH)` before the attack | attacker borrows 550e18 (650 available, 1st bot withdrawal of 100 ok); 2nd bot withdrawal `blocked`; vault idle WETH 150e18; available 0 |
| T2-34 | chain | `::test_usdc_variant` | variant `usdc` | lend-eth USDC available 0; lend-eth WETH available 800e18 unchanged |
| T2-40 | chain | `test_t2_normal_chain.py::test_normal_safe` | `run_normal(ticks=60, seed=7, tick_s=0)` | for each block of `[start_block; end_block]`, `getReservesData(block_identifier=b)`: util ≤ 8500 on USDC/WETH; 0 `Released` events with `backed == false`; `backingRatioBps() == 10000`; rsETH supply 1400e18 |
| T2-41 | chain | `::test_normal_run_record` | same | `data/runs/<run_id>.json` written by the end of the call (blocking); label normal, `attack_start_block is None`, `phase_blocks == {}`, 4 keys in `treasury_supplied_at_start`; emitted steps include `bridge_deposit` and `large_deposit` (status ok) |
| T2-50 | API | `test_t2_demo_api.py::test_attack_starts_run` | `TestClient(app)`, `USE_FIXTURES=False`, `FakeRunner` that records argv | body `{}`: 200, `kind=="attack"`, `status=="running"`, `1 ≤ seed ≤ 999999`, argv contains `-m scenario.attack --json --run-id <run_id> --variant default --seed <seed>`, `run_id` ends with `-attack-<seed>`; body `{"seed": 0}`: `seed == 0`, `params["chunk_weth"] == 100`; body `{"seed": 42}`: `seed == 42` |
| T2-51 | API | `::test_log_and_exit_done` | Fake emits `{"step":"forged_mint","block":12,"msg":"x",…}` then exit 0 | GET → `log == ["[12] forged_mint: x"]`, `status=="done"`, `finished_at` not null |
| T2-52 | API | `::test_exit_nonzero_failed` | exit 3 | `status=="failed"`, last line `"exit code 3"` |
| T2-53 | API | `::test_reset_calls_store_reset_only_on_success` | `_reset_store` patched (counter) | exit 0 → 1 call; exit 1 → 0 calls |
| T2-54 | API | `::test_404_and_409_and_422` | — | unknown run 404 `{"detail": "run not found"}`; 2nd attack (or reset) while `running` 409; `variant="foo"` 422; `seed=-1` 422 |
| T2-55 | API | `::test_fixture_mode` | `USE_FIXTURES=True` | response == `fixtures/demo_run.json`; runner never called |

#### Definition of done

- [ ] `make test-t2` green with anvil + `make deploy` (0 skips) and without a chain (chain tests skipped, the rest green).
- [ ] `make reset && make attack` on local reproduces the T2-30 numbers.
- [ ] `make seed` twice in a row: the 2nd sends no transaction.
- [ ] `make attack SEED=42` and `SEED=43` give different params and two valid `data/runs/*.json`.
- [ ] `make normal MINUTES=2` on local runs without exception, returns at the end and writes a `data/runs/*.json` with label `normal`.
- [ ] Engine on (`make demo`), `make reset` then `make seed`: no alert or decision created during the seed; `data/runtime/local/maintenance.flag` absent at the end, including after an interrupted seed (Ctrl-C).
- [ ] Roles funded on Fuji via `make fund-roles` (T1); one seed + one default attack played once on Fuji; snowtrace links of the `forgedRelease` and `setReserveFrozen` txs noted for T9.
- [ ] Front button (or `curl -X POST :8000/api/demo/attack -H 'content-type: application/json' -d '{"seed": null}'`) → `DemoRun` with a seed drawn in [1; 999999], which goes `done`, logs visible; a 2nd call during the run → 409.
- [ ] `POST /api/demo/reset` on fuji redeploys (`make deploy FORCE=1`) then re-seeds without intervention.
- [ ] `scenario/_compat.py` deleted if T0 delivered the 2.4 helpers.

#### Known pitfalls

- **Seed order** (3.2): bots[1]'s USDC collateral (4,500,000 / 3,000,000) must be deposited **before** the borrows, otherwise `borrow` reverts "insufficient collateral". Never "fix" it by touching the oracle: the 2.2 prices do not move.
- Collateral and liquidity are two separate balances: `depositCollateral(USDC)` increases `total_collateral`, not `total_supplied` or `available_liquidity`. Do not use `supply` for collateral.
- **bots[1] no longer borrows after the seed**: only bots[2] borrows in normal traffic (bots[1]'s margin is part of the reference state).
- **Maintenance mode**: always in a `finally`; a forgotten `maintenance.flag` file turns off all detection (the engine no longer evaluates any rule). When in doubt: `rm data/runtime/<network>/maintenance.flag`. Do not nest two `maintenance()` (hence `run_seed(manage_maintenance=False)` in the reset).
- `TreasuryVault.supply` uses the vault's balance: mint (or transfer) the tokens **to the vault** before `vault.supply`, otherwise revert.
- `MiniLend.withdraw` of an exact amount reverts "insufficient balance" if the amount exceeds the bot's position, "insufficient liquidity" if it exceeds liquidity: only the second is expected (`blocked`) during the rush; the first is a scenario bug (`failed`).
- `chain.send` calls `estimate_gas`: a revert raises `ContractLogicError` **before** sending (no status 0 receipt). Blocked bot withdrawals must be caught (`expect_revert=True`).
- `approve` before `supply`, `bridge.deposit`, `depositCollateral`, `repay`. USDC has 6 decimals.
- Nonces: one process per role. Never run `normal` and `attack` at the same time (shared bots[0]); the API refuses concurrent runs.
- On fuji, `make deploy` without `FORCE=1` refuses to overwrite the existing deployment: `reset` always passes `FORCE=1`. Warn the team, addresses change.
- After `make reset`, addresses change: always call `chain.lending()`, `token()`… again on each run, do not keep a `Contract` object in a global variable.
- Subprocesses: `PYTHONUNBUFFERED=1` and `flush=True`, otherwise logs arrive at the end.
- `RunRecord.params` does not accept lists: `"4,5"`.
- `fixtures/deployments.example.json` uses `Bridge`/`Oracle`; 2.3 is authoritative (`MockBridge`/`MockOracle`).
- Fuji: default attack ≈ 3 min (warmup 24 s + 6 borrows × 8 s + freeze at 80 s); public RPC is rate-limited, use a provider RPC.
- **Non-circularity**: no attack parameter may be chosen by looking at the thresholds of 2.7/rules.yaml (T2-05 checks this). The draw ranges above are the only reference.
- If T4's reaction is active, liquidity drops faster (the vault withdraws 150 WETH): the loop re-reads liquidity every iteration (T2-33).

#### Later (phase 2)

- Variants: drain on lend-avax, single-block attack (flash), slow bleed, multiple attackers, oracle manipulation.
- Liquidations in normal traffic, more realistic traffic profiles (quiet periods, bursts).
- Replay of the mainnet incident (with T7).

#### Claude Code starter prompt

```
You are working on task T2 (scenario: seed, attack, normal traffic, reset) of TASKS.md.
1. Read TASKS.md sections 1 and 2, then the whole T2 section. Read backend/models.py,
   backend/settings.py, backend/chain.py, fixtures/run_record.example.json, fixtures/demo_run.json.
   Do NOT read backend/config/rules.yaml to tune the attack (non-circularity).
2. Modify ONLY: scenario/* (except scenario/__init__.py, owned by T0), backend/api/demo.py, mk/t2.mk, backend/tests/test_t2_*.py.
   For any change elsewhere or to the contract (section 2), do not edit: write the request
   in docs/contract-requests.md and tell me.
3. Start with the pure tests (T2-01 to T2-11, T2-50 to T2-55), then the code that makes them pass.
   If backend/chain.py does not have token()/vault()/bridge()/oracle()/bot_accounts() yet,
   create scenario/_compat.py based on chain.contract() and chain.load_deployment().
4. Then the chain tests (T2-20 to T2-41): they must skip without anvil.
   Once T1 has delivered, run `anvil` then `NETWORK=local make deploy` and make them pass.
5. Follow the numbers of the T2 section exactly (3.1, 3.2, expected attack values).
   No call to setPriceE8 or setGuardian: the seed deposits the USDC collateral before the borrows
   and runs under data/runtime/<network>/maintenance.flag (created at the start, deleted in a finally).
6. Before each commit: make test-t2 green (pytest backend/tests/test_t2_*.py, never -k).
   Push often after each green test.
```


---
### T3 · Monitoring engine: collector, rules R1 to R5, state API

**Goal.** Read the chain state at every new block (a `Snapshot`), apply the five simple rules R1 to R5 from section 2.7 over a sliding window, emit `Alert`s without duplicates, pass them to subscribers (T4) and serve `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` from the store when `USE_FIXTURES=false`. One indicator per rule, nothing more in the MVP.

**Depends on.**
- T0 → `backend/models.py`, `settings.py`, `chain.py`, `store.py` (including `Store.generation`, incremented by `reset()`), `main.py`, fixtures → while waiting for `backend/store.py`: the `MemStore` class written in your tests (see T3-12, with its own `generation`); while waiting for `main.py` wiring: `make monitor` runs the loop alone.
- T1 → contracts, `deployments/<network>.json`, `abi/*.json` → meanwhile: `fixtures/snapshots_attack.jsonl` and `snapshots_normal.jsonl` (rules, engine and API are fully testable without a chain); the collector test on anvil is `skip` as long as `deployments/local.json` does not exist or the vault has deposited nothing (`getUserSupplied(vault, WETH) == 0` on `lend-eth`).
- T2 → `make seed` (vault positions on anvil) and the file `data/runtime/<network>/maintenance.flag` created at the start of `seed`/`reset` and removed in a `finally` (2.10) → meanwhile: same fixtures; tests create and remove the file themselves.

**Unblocks.** T4 (receives `(alerts, snapshot)` via `Engine.on_alerts`, called through `await asyncio.to_thread(handler, alerts, snapshot)` one call at a time, uses `rules_version`), T2 (maintenance mode keeps `seed`/`reset` from looking like an attack), T5 (reads `store.alerts()`, `store.latest_snapshot()`), T6 (the four T3 routes in live mode), T7 (reads `/api/alerts` for detection and detection delay), T9 (demo figures).

**Owned files.** `backend/collector.py`, `backend/rules.py`, `backend/engine.py`, `backend/config/rules.yaml`, `backend/api/state.py`, `backend/tests/test_t3_*.py`, `mk/t3.mk`.

**Read before starting.** TASKS.md sections 1.2, 1.5, 2.2 (MiniLend, MockBridge, MockOracle, TreasuryVault), 2.3, 2.4, 2.5, 2.6, 2.7, 2.9, 2.10; `backend/models.py` (Snapshot, Alert, StateResponse, SeriesPoint, Health); `backend/chain.py`; both `fixtures/snapshots_*.jsonl` files (one line = one JSON `Snapshot`, one snapshot every 2 blocks, blocks 45201800 to 45201880).

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Contract addresses | `deployments/<network>.json` (2.3), re-read every loop via `chain.load_deployment()` | T1 | none needed for rules/engine/API; collector: `skip` |
| ABIs | `abi/MiniLend.json`, `MockERC20.json`, `RsETH.json`, `MockBridge.json`, `MockOracle.json`, `TreasuryVault.json` | T1 | same |
| Populated local chain | anvil + `make deploy` + `make seed` (positions 150 WETH + 400,000 USDC on `lend-eth`, 100 WETH + 300,000 USDC on `lend-avax`) | T1, T2 | jsonl fixtures |
| Snapshot series | `fixtures/snapshots_attack.jsonl` (without our reaction), `snapshots_normal.jsonl` | T0 (final) | — |
| Store | `backend.store.store` (2.10), including `generation` | T0 | test-local `MemStore` |
| Maintenance mode | presence of the file `settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag"` (2.10) | T2 | created and removed by the tests |
| Variables | `NETWORK`, `RPC_URL`, `RPC_FALLBACK_URL`, `CHAIN_ID`, `USE_FIXTURES`, `ENGINE_ENABLED`, `POLL_INTERVAL_S` | `.env` | defaults from `settings.py` |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `Snapshot` (source `"live"`) | `models.Snapshot`, stored by `store.add_snapshot` | T3 (rules), T4, T5, T6 via `/api/state` |
| `Alert` | `models.Alert`, id `ALT-<network>-<block>-<rule_id>-<deployment_id or global>-<asset or all>`, stored by `store.add_alerts` | T4 (`on_alerts`), T5, T6, T7 |
| Subscriber call | `handler(new_alerts: list[Alert], snapshot: Snapshot)`, only if `new_alerts` is non-empty; in `run_forever`: `await asyncio.to_thread(handler, new_alerts, snapshot)`, one call at a time, in snapshot order | T4 (`responder.handle`) |
| `rules_version` | `"sha256:" + sha256(exact bytes of backend/config/rules.yaml)` (71 characters) | T4 (decision), T7, T9 |
| `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` | `Health`, `StateResponse`, `SeriesPoint[]`, `Alert[]` (2.9) | T6, T7 |
| `make test-t3`, `make monitor-once`, `make monitor`, `make replay-t3` | targets in `mk/t3.mk` | everyone (debug) |

#### Detailed specification

**1. `backend/config/rules.yaml`.** Byte-for-byte copy of the YAML block from 2.7 (with the trailing newline). Any change alters `rules_version`: this is intended (the T4 evidence references the version).

**2. `backend/rules.py` (pure functions, no network call, no clock).**

```python
SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
RULES_PATH = settings.CONFIG_DIR / "rules.yaml"

def rules_version(path: Path = RULES_PATH) -> str          # "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
def load_rules(path: Path = RULES_PATH) -> dict             # yaml.safe_load + cfg["_version"] = rules_version(path)
def treasury_positions(s: Snapshot) -> dict[tuple[str, str], PositionSnapshot]   # (deployment_id, asset) -> position, supplied > 0 only
def position_value(s: Snapshot, deployment_id: str, asset: str) -> float          # 0.0 if no position
def deployment_exposure(s: Snapshot, deployment_id: str) -> float                 # sum of value_usd of the deployment's positions
def collateral_exposure(s: Snapshot, token: str) -> tuple[float, list[str]]      # deployments where reserve(token).ltv_bps > 0; sum of their positions
def evaluate_r1(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r2(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r3(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r4(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_r5(window: list[Snapshot], cfg: dict) -> list[Alert]
def evaluate_all(window: list[Snapshot], cfg: dict) -> list[Alert]   # concatenates R1..R5 (enabled rules), sorted (rule_id, deployment_id or "", asset or "")
```

Shared conventions: `s = window[-1]`; a rule with `enabled: false` returns `[]`; an empty `window` returns `[]`. Each alert: `network=s.network`, `block_number=s.block_number`, `block_time=s.block_time`, `detected_at=s.block_time` (the engine replaces it), `rules_version=cfg["_version"]`, `id` built with `make_alert_id(s, rule_id, deployment_id, asset)`. Displayed amounts are converted to human units (`int(x) / 10**decimals`), formatted `f"{v:,.0f}"` if integer, otherwise `f"{v:,.2f}"`; percentages with one decimal (`19.4 %`, space before `%`). `metrics` contain only `int`, `float` or `str` (no `bool`).

| Rule | Algorithm | `metrics` | `title` / `explanation` (English) |
|---|---|---|---|
| R1 | for each `TokenSnapshot` with `backing_ratio_bps is not None` and `< min_backing_ratio_bps` → critical; `deployment_id=None` (JSON `null`, global alert), `asset=symbol` (`"rsETH"`); exposure = `collateral_exposure(s, symbol)` | `backing_ratio_bps`, `backing` (human float), `total_supply` (float), `threshold_bps`, `exposed_deployments` (`"lend-eth,lend-avax"`) | `"rsETH backing below threshold"` / `"rsETH backing fell to 19.4 % (1,200 WETH backing for 6,200 rsETH supply)."` |
| R2 | for each `borrowable` reserve of `s` with a vault position: `hist` = `int(available_liquidity)` of that reserve in each window snapshot that contains it; if `len(hist) < 2` or `max(hist) == 0` → nothing; `drop_bps = (max - cur) * 10000 // max`; `>= critical_drop_pct*100` → critical, else `>= high_drop_pct*100` → high | `available_liquidity`, `max_available_liquidity` (human floats), `drop_pct` (`drop_bps/100`), `window_snapshots` | `"WETH liquidity dropping on lend-eth"` / `"Available WETH liquidity on lend-eth fell 37.5 % within the last 20 snapshots (from 800 to 500 WETH)."` |
| R3 | `borrowable` reserves with a position: `utilization_bps >= critical_bps` → critical, else `>= warning_bps` → warning | `utilization_bps`, `threshold_bps` | `"WETH utilization high on lend-eth"` / `"WETH utilization on lend-eth reached 94.4 % (threshold 90.0 %)."` |
| R4 | each position (`supplied > 0`): `withdrawable_ratio_bps < critical_below_bps` → critical, else `< high_below_bps` → high | `withdrawable_ratio_bps`, `withdrawable_now`, `supplied` (human floats), `threshold_bps` | `"Our WETH position on lend-eth is stuck"` / `"Only 66.7 % of our 150 WETH position on lend-eth can be withdrawn now (100 WETH)."` |
| R5 | if `len(window) >= 2`: for each reserve of `s` whose deployment holds a vault position, `prev` = same reserve in `window[-2]`; high alert if `(r.frozen or r.paused)` and `not (prev.frozen or prev.paused)`; exposure = `deployment_exposure` | `state` (`"frozen"`, `"paused"` or `"frozen+paused"`) | `"rsETH reserve frozen on lend-eth"` / `"The rsETH reserve on lend-eth was frozen; our positions on lend-eth are worth 775,000 USD."` |

R2, R3, R4 exposure = `position_value(s, deployment_id, asset)`.

```python
class AlertLatch:
    """Deduplication from 2.7: one emission per (rule_id, deployment_id, asset) and per severity."""
    def __init__(self) -> None: self._active: dict[tuple[str, str | None, str | None], str] = {}
    def filter(self, candidates: list[Alert]) -> list[Alert]
    def active(self) -> dict[tuple[str, str | None, str | None], str]
    def reset(self) -> None
```

`filter` receives **all** candidates of the snapshot (all rules together): a missing key → removed from `_active` (the condition went away); a new key → emitted; a present key with strictly higher severity → emitted and updated; same or lower severity → nothing (the remembered severity is never downgraded). Output order = candidate order.

**3. `backend/collector.py`.**

```python
def build_snapshot(block_number: int, client: Web3 | None = None) -> Snapshot   # default client chain.w3()
def ratio_bps(part: int, whole: int) -> int     # rounded to nearest, integer: (part*10000 + whole//2) // whole; 0 if whole == 0
def struct_to_dict(abi: list, fn_name: str, value: tuple) -> dict   # names the ReserveData tuple fields from the ABI components
```

Algorithm (all `.call(block_identifier=block_number)` for a consistent state; contracts built with `client.eth.contract(address, abi=chain.load_abi(name))` so the fallback client can be passed):
1. `dep = chain.load_deployment()`; `addr_to_symbol` = inverse of `dep["assets"]` (lowercase addresses); `vault_addr = dep["contracts"]["TreasuryVault"]`.
2. Per asset: `decimals` (module cache, keyed by address), `price_usd = oracle.getPriceE8(asset) / 1e8` (once per snapshot; revert `"Oracle: no price"` → `0.0` + WARNING log).
3. Per deployment in `dep["lending"]`: **one** `getReservesData()` call; for each entry → `ReserveSnapshot(deployment_id, asset=symbol, asset_address, decimals, total_supplied=str(totalSupplied), total_borrowed, available_liquidity, total_collateral, utilization_bps=utilizationBps, supply_apy_bps=supplyRateBps, borrow_apy_bps=borrowRateBps, ltv_bps=ltvBps, borrowable, frozen, paused, price_usd)`. Unknown address → ignored, WARNING log.
4. For each `borrowable` reserve: `supplied = getUserSupplied(vault_addr, asset)`; if `supplied > 0` → `withdrawable = min(supplied, available_liquidity)`, `PositionSnapshot(wallet=vault_addr, …, withdrawable_ratio_bps=ratio_bps(withdrawable, supplied), value_usd=round(supplied/10**dec*price, 2), withdrawable_usd=round(withdrawable/10**dec*price, 2))`.
5. Tokens: `totalSupply()` of each symbol; for `rsETH`: `backing = bridge.totalBacking()`, `backing_ratio_bps = bridge.backingRatioBps()` (on-chain value, rounded down: 1200/6200 → 1935, as in the fixtures); other tokens: `None`.
6. Vault: `VaultStatus(address=vault_addr, deposits_paused=vault.depositsPaused(), idle_balances={symbol: str(token.balanceOf(vault_addr))} for each symbol in dep["assets"])`.
7. `block_time = datetime.fromtimestamp(client.eth.get_block(block_number)["timestamp"], tz=timezone.utc)`; `network=settings.NETWORK`, `chain_id=settings.CHAIN_ID`, `source="live"`.
8. Any RPC exception propagates as is (no partial snapshot). About 20 RPC calls per snapshot.
9. `python -m backend.collector --once [--block N]` prints the snapshot as JSON (`model_dump_json(indent=2)`); without `--block`, uses `client.eth.block_number`.

**4. `backend/engine.py`.**

```python
@dataclass
class EngineStatus:
    running: bool = False; rpc_ok: bool = False; rpc_url: str = ""; last_block: int = 0
    last_update: datetime | None = None; last_error: str | None = None; consecutive_errors: int = 0
    maintenance: bool = False; pending_handlers: int = 0
STATUS = EngineStatus()          # read by backend/api/state.py (internal to T3)

class Engine:
    def __init__(self, store, cfg: dict | None = None, clock: Callable[[], datetime] | None = None): ...
    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None
    def process(self, snapshot: Snapshot) -> list[Alert]   # ingest + SYNCHRONOUS subscriber call (tests, --replay)
    def ingest(self, snapshot: Snapshot) -> list[Alert]    # rules + store, without calling subscribers (used by run_forever)
    def reset(self) -> None                   # clears window and latch
    def in_maintenance(self) -> bool          # maintenance_flag_path().exists()
    def stop(self) -> None
    async def run_forever(self) -> None
    def _make_client(self, url: str) -> Web3  # replaceable in tests

def maintenance_flag_path() -> Path           # settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag" (re-read on every call)
```

`cfg` defaults to `rules.load_rules()`; `clock` defaults to `lambda: datetime.now(timezone.utc)`; the window holds the **last** `cfg["window_blocks"]` (= 20) **snapshots** (not blocks: on anvil `--block-time 1` with `POLL_INTERVAL_S=2`, that is one snapshot every ~2 blocks, like the fixtures).

`ingest(snapshot)` (in this order):
1. **Generation.** `g = getattr(store, "generation", 0)`; if `g != self._generation` → `reset()`, `self._generation = g`, INFO log `"store generation changed, window reset"` (a T2 `store.reset()` cleared everything). `self._generation` is initialised in `__init__` with the store's current generation.
2. **Duplicate / going backwards.** If `snapshot.block_number == self._last_block` → `return []` (already processed). If `<` → the chain was reset: `reset()` then WARNING log `"chain went backwards, window reset"`. `self._last_block = snapshot.block_number` (also tracked during maintenance).
3. **Maintenance mode.** If `in_maintenance()`: `store.add_snapshot(snapshot)`, `self._maintenance = True`, `STATUS.maintenance = True`, INFO log `block=… maintenance=on`, `return []`: **no rule evaluated**, the snapshot does not enter the window. Otherwise, if `self._maintenance` was true (the file just disappeared) → `reset()`, `self._maintenance = False`, `STATUS.maintenance = False`, INFO log `"maintenance ended, window reset"`, then continue normally with this snapshot.
4. Append to the window, truncate to `window_blocks`.
5. `new = latch.filter(rules.evaluate_all(window, cfg))`, then `detected_at = clock()` on each alert (`model_copy(update=…)`).
6. `store.add_snapshot(snapshot)`; if `new`: `store.add_alerts(new)`.
7. INFO log `block=45201812 positions=4 new_alerts=1` and one WARNING per alert: `ALERT critical R1_BACKING_DROP global/rsETH exposure=1325000 | rsETH backing fell to…`. Returns `new`.

`process(snapshot)` = `new = ingest(snapshot)` then, if `new`, each handler called directly inside a `try/except` (`logger.exception`, continue). Reserved for tests and `--replay` (no event loop); the production loop goes through `ingest` + the dispatcher below.

`run_forever()`:
1. `STATUS.running = True`; primary client `RPC_URL`; creates `self._queue: asyncio.Queue[tuple[list[Alert], Snapshot]]` and starts the **dispatcher** task `self._dispatcher()`.
2. Loop until stopped: re-read `chain.load_deployment()` (missing file → WARNING, wait); if `(deployed_at_block, contracts.TreasuryVault)` changed since the previous round → `reset()` (a `make reset` redeployed). `head = await asyncio.to_thread(lambda: client.eth.block_number)`; if `head > last_block` → `snap = await asyncio.to_thread(collector.build_snapshot, head, client)` then `new = await asyncio.to_thread(self.ingest, snap)`; if `new` → `self._queue.put_nowait((new, snap))`, `STATUS.pending_handlers = self._queue.qsize()`. Success → `rpc_ok=True`, `consecutive_errors=0`, `last_block`, `last_update`.
3. Exception → `rpc_ok=False`, `last_error=str(e)[:200]`, `consecutive_errors += 1`, WARNING. At 3 consecutive errors and if `RPC_FALLBACK_URL` is non-empty → switch to the fallback (`STATUS.rpc_url` updated, WARNING `"switching to fallback RPC"`). Every 30 rounds on the fallback, retry the primary.
4. `await asyncio.sleep(settings.POLL_INTERVAL_S)`. Only the head block is processed (no block-by-block catch-up).
5. `_dispatcher()`: loop `alerts, snap = await self._queue.get()` then, for each handler in registration order, `await asyncio.to_thread(handler, alerts, snap)` inside a `try/except` (`logger.exception`, continue). A single dispatcher task → **one call at a time, in snapshot order** (2.10); collection and the API keep running while a slow response (T4 Fuji transactions) executes. `stop()` stops the loop; the dispatcher finishes the current item and is then cancelled.
6. `python -m backend.engine --loop` (loop alone, T0 store); `python -m backend.engine --replay <file.jsonl>` (replays a jsonl into a fresh `Engine` via `process` and prints one line per alert: `block rule_id severity deployment/asset exposure explanation`).

Startup in the API: `backend/main.py` (T0) creates `engine = Engine(store)`, wires `engine.on_alerts(responder.handle)` and, if `settings.ENGINE_ENABLED`, starts `asyncio.create_task(engine.run_forever())` at startup. T3 does not modify `main.py`.

**5. `backend/api/state.py`.** Read `settings.USE_FIXTURES` **on every request** (not at import, otherwise tests cannot switch it). `true` → current behaviour (fixtures). `false`:
- `/health`: `Health(status="ok" if STATUS.running and STATUS.rpc_ok else "degraded", network=settings.NETWORK, chain_id=settings.CHAIN_ID, block_number=latest snapshot or 0, rpc_ok=STATUS.rpc_ok, engine_running=STATUS.running, version="0.1.0")`.
- `/state`: no snapshot → `503 {"detail": "no snapshot yet"}` (exact code and message from the error table in 2.9; the front end shows "Waiting for first block"). Otherwise `StateResponse` with `updated_at = STATUS.last_update or latest.block_time`, `open_incident_id` = id of the first incident in `store.incidents()` whose `status != "resolved"` (else `None`), `vault/positions/reserves/tokens` copied, `totals = compute_totals(latest)` and `risk_level = compute_risk_level(store)`. All model keys are present (`null` if empty, never `exclude_none`, 2.5).
- `compute_totals(s: Snapshot) -> dict[str, float]` (pure, tested on its own), exact definitions from 2.6, each value rounded to 2 decimals:
  - `idle_usd` = Σ over `s.vault.idle_balances` of `int(balance) / 10**decimals * price_usd` (decimals and price from the `TokenSnapshot` of the same symbol; unknown symbol → ignored, WARNING log);
  - `withdrawable_usd` = Σ `withdrawable_usd` of the positions;
  - `value_usd` = Σ `value_usd` of the positions **+ `idle_usd`**;
  - `at_risk_usd` = Σ (`value_usd` − `withdrawable_usd`) **of the positions** (money pulled back to the vault is never at risk).
- `compute_risk_level(store) -> str`: maximum severity of the conditions **still true** at the latest snapshot (2.6) = `max(SEVERITY_RANK)` over `rules.evaluate_all(window, cfg)` recomputed without latch on the store's last `window_blocks` snapshots (sorted by `block_number`); `"info"` if none. An alert whose condition went away no longer counts. If the latest snapshot was stored in maintenance mode (`STATUS.maintenance`), `"info"`.
- `/series`: store snapshots (≤ `limit`, chronological order) containing the reserve `(deployment_id, asset)` → `SeriesPoint(block_number, block_time, utilization_bps, available_liquidity, supply_apy_bps, withdrawable_ratio_bps` of the position if it exists else `None`, `backing_ratio_bps` from the rsETH `TokenSnapshot`). Unknown reserve → `[]`. `limit: int = Query(300, ge=1, le=2000)`.
- `/alerts`: `store.alerts(since_block)` sorted by `(block_number, rule_id)` descending (most recent first).

**6. `mk/t3.mk`.** Never redefines `NETWORK` (it comes from `.env`, exported by the root `Makefile`, or from the command line).

```make
test-t3:      ; python -m pytest -q backend/tests/test_t3_*.py
monitor-once: ; python -m backend.collector --once
monitor:      ; python -m backend.engine --loop
replay-t3:    ; python -m backend.engine --replay $(or $(FILE),fixtures/snapshots_attack.jsonl)
```

#### Tests that must pass

Command: `make test-t3` (= `python -m pytest -q backend/tests/test_t3_*.py`, never `-k`). Shared loading: `snaps = [Snapshot.model_validate_json(l) for l in open("fixtures/snapshots_attack.jsonl")]`; `win(b)` = the 20 snapshots ending at block `b`. Fixed clock `clock = lambda: datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)`. Tests that touch the real store do `store.reset()` and `monkeypatch.setattr(settings, "DATA_DIR", tmp_path)`; the temporary `DATA_DIR` also guarantees no leftover `maintenance.flag` skews the tests.

| Id | File :: function | Setup | Expected result |
|---|---|---|---|
| T3-01 | `test_t3_rules.py::test_rules_yaml_matches_contract` | — | `yaml.safe_load` == dict from 2.7; `rules_version()` starts with `sha256:`, length 71, equal to the sha256 of the file bytes |
| T3-02 | `test_t3_rules.py::test_exposure_helpers` | `s = snaps[0]` | `collateral_exposure(s, "rsETH") == (1325000.0, ["lend-eth", "lend-avax"])`; `deployment_exposure(s, "lend-eth") == 775000.0`; `"lend-avax"` → `550000.0`; `len(treasury_positions(s)) == 4` |
| T3-03 | `test_t3_rules.py::test_r1_backing_drop` | `win(45201810)`, `win(45201812)` | 810 → `[]`; 812 → 1 critical alert, `id == "ALT-fuji-45201812-R1_BACKING_DROP-global-rsETH"`, `deployment_id is None`, `asset == "rsETH"`, `block_number == 45201812`, `metrics["backing_ratio_bps"] == 1935`, `exposure_usd == 1325000.0`, `"19.4 %"` in `explanation` |
| T3-04 | `test_t3_rules.py::test_r2_liquidity_drop` | `win(45201824)`, `win(45201826)`, `win(45201832)` | 824 (600 WETH, -25%) → `[]`; 826 → high, `drop_pct == 37.5`, `max_available_liquidity == 800.0`, `available_liquidity == 500.0`; 832 → critical, `drop_pct == 62.5`; `exposure_usd == 375000.0`; never an R2 alert on `lend-avax` nor on USDC |
| T3-05 | `test_t3_rules.py::test_r3_utilization` | `win(45201834/836/838)` | 834 (8947 bps) → `[]`; 836 → warning, `utilization_bps == 9444`; 838 → critical, `10000` |
| T3-06 | `test_t3_rules.py::test_r4_position_stuck` | same | 834 → `[]`; 836 → high, `withdrawable_ratio_bps == 6667`, `withdrawable_now == 100.0`; 838 → critical, `0`; `exposure_usd == 375000.0` |
| T3-07 | `test_t3_rules.py::test_r5_reserve_frozen` | `win(45201876/878/880)` | 876 → `[]`; 878 → 1 high alert `lend-eth`/`rsETH`, `exposure_usd == 775000.0`, `metrics["state"] == "frozen"`; 880 → `[]` |
| T3-08 | `test_t3_rules.py::test_disabled_rule_and_empty_window` | `cfg["R1_BACKING_DROP"]["enabled"] = False` | `evaluate_r1(win(45201812), cfg) == []`; `evaluate_all([], cfg) == []` |
| T3-09 | `test_t3_rules.py::test_alert_latch` | synthetic alerts with the same key | high → emitted; high → nothing; critical → emitted; high → nothing; absent → key removed; high → re-emitted |
| T3-10 | `test_t3_engine.py::test_attack_replay_expected_alerts` | `Engine(MemStore(), clock=clock)`, `process` on the 41 snapshots | exactly 8 alerts, in this order: `(45201812, R1_BACKING_DROP, None, rsETH, critical, 1325000)`, `(45201826, R2_LIQUIDITY_DROP, lend-eth, WETH, high, 375000)`, `(45201832, R2…, critical)`, `(45201836, R3_UTILIZATION_HIGH, lend-eth, WETH, warning)`, `(45201836, R4_POSITION_STUCK, lend-eth, WETH, high)`, `(45201838, R3…, critical)`, `(45201838, R4…, critical)`, `(45201878, R5_RESERVE_FROZEN, lend-eth, rsETH, high, 775000)`; no duplicate `(rule_id, deployment_id, asset, severity)`; no alert with `deployment_id == "lend-avax"`; all have `detected_at == clock()` |
| T3-11 | `test_t3_engine.py::test_normal_replay_no_alert` | same with `snapshots_normal.jsonl` | `0` alerts (max utilization 6000 bps, max liquidity drop 13.6%, backing 10000) |
| T3-12 | `test_t3_engine.py::test_handlers_and_store` | `MemStore` (in-memory lists, same methods as 2.10, `generation = 0` incremented by `reset()`); one handler that records, one that raises | handler called 6 times (blocks 812, 826, 832, 836, 838, 878); the second one's exception interrupts nothing; store: 41 snapshots, 8 alerts |
| T3-13 | `test_t3_engine.py::test_duplicate_and_backwards_blocks` | replay `snaps[5]` twice; then `snaps[0]` after `snaps[40]` | duplicate → `[]`; going backwards → window of size 1, empty latch |
| T3-14 | `test_t3_engine.py::test_rpc_fallback` | `POLL_INTERVAL_S=0`, `RPC_FALLBACK_URL="http://fallback"`, `_make_client` returns a fake client that raises `ConnectionError` for the primary, returns `block_number=45201812` for the fallback; `collector.build_snapshot` monkeypatched → `snaps[6]`; `stop()` after the first `process` | `STATUS.rpc_url == "http://fallback"`, `STATUS.rpc_ok`, 1 R1 alert produced, `asyncio.wait_for(…, 2)` does not raise |
| T3-15 | `test_t3_collector.py::test_ratio_bps` | — | `ratio_bps(100*10**18, 150*10**18) == 6667`; `ratio_bps(0, 5) == 0`; `ratio_bps(5, 0) == 0`; `ratio_bps(150, 150) == 10000` |
| T3-16 | `test_t3_collector.py::test_snapshot_on_anvil` | `skipif` if `deployments/local.json` is missing, anvil is unreachable, or `getUserSupplied(vault, WETH)` == 0 on `lend-eth` (not seeded yet); after `make chain deploy seed` | 6 reserves; 4 positions (lend-eth WETH 150, USDC 400,000; lend-avax WETH 100, USDC 300,000), all `withdrawable_ratio_bps == 10000`; rsETH `backing_ratio_bps == 10000`; lend-eth WETH `utilization_bps == 6000`; `source == "live"`, `network == "local"`, `chain_id == 31337`; sum of `value_usd == 1325000.0` |
| T3-17 | `test_t3_api.py::test_fixture_mode` | `USE_FIXTURES=True`, `TestClient(app)` | 200 on the 4 routes, responses validated by the models (no figures: fixtures regenerated) |
| T3-18 | `test_t3_api.py::test_live_mode_attack` | `USE_FIXTURES=False`, T0 store reset, `Engine(store, clock=clock)` on the 41 attack snapshots | `/api/state`: `block_number == 45201880`, `totals == {"value_usd": 1325000.0, "withdrawable_usd": 950000.0, "idle_usd": 0.0, "at_risk_usd": 375000.0}`, `risk_level == "critical"`; `/api/alerts`: 8 items, the first at block 45201878 (R5), the last at block 45201812; `?since_block=45201836` → 5; `/api/series?deployment_id=lend-eth&asset=WETH`: 41 points, first `available_liquidity == "800000000000000000000"`, last `"0"`, last `withdrawable_ratio_bps == 0`, `backing_ratio_bps == 1935`; `limit=5` → 5 points, the last at block 45201880; `asset=DAI` → `[]`; `/api/health`: `engine_running is False`, `status == "degraded"`, `block_number == 45201880` |
| T3-19 | `test_t3_api.py::test_live_mode_normal_and_empty` | same with the normal jsonl; then empty store | normal: `risk_level == "info"`, `at_risk_usd == 0.0`, `withdrawable_usd == 1325000.0`, `idle_usd == 0.0`; empty store: `/api/state` → 503 with `{"detail": "no snapshot yet"}`, `/api/alerts` → `[]` |
| T3-20 | `test_t3_api.py::test_totals_and_risk_definitions` | `s = snaps[40]`; `s2 = s` with `vault.idle_balances["WETH"] = str(10 * 10**18)` (`model_copy`) | `compute_totals(s) == {"value_usd": 1325000.0, "withdrawable_usd": 950000.0, "idle_usd": 0.0, "at_risk_usd": 375000.0}`; `compute_totals(s2)`: `idle_usd == 25000.0`, `value_usd == 1350000.0`, `at_risk_usd == 375000.0` (unchanged); store with the 41 attack snapshots then 20 copies of `snaps[0]` at blocks 45201882… (conditions gone) → `compute_risk_level(store) == "info"` |
| T3-21 | `test_t3_engine.py::test_maintenance_mode` | `DATA_DIR=tmp_path`; create `tmp_path/runtime/fuji/maintenance.flag`; `Engine(MemStore(), clock=clock)`; `process(snaps[0..10])`; remove the file; `process(snaps[11])` | while the file exists: 0 alerts (even though R1 is true from 45201812), handler never called, store: 11 snapshots, `STATUS.maintenance is True`, empty window; after removal: window of size 1, 1 critical R1 alert at block 45201822, `STATUS.maintenance is False` |
| T3-22 | `test_t3_engine.py::test_generation_change_resets_window` | `MemStore()`; `process(snaps[0..6])` (R1 emitted at 812); `store.reset()` (`generation` 0 → 1); `process(snaps[7])` | after the reset: window of size 1, latch cleared, R1 re-emitted at block 45201814; without `store.reset()`, `snaps[7]` produces nothing (control) |
| T3-23 | `test_t3_engine.py::test_handlers_off_loop_one_at_a_time` | `POLL_INTERVAL_S=0`; fake client that successively returns the blocks of `snaps[6]`, `snaps[16]`, `snaps[19]` (812, 832, 838); `build_snapshot` monkeypatched; slow handler (`time.sleep(1.0)`) that records its thread, the block order and the number of concurrent calls; meanwhile, `httpx.AsyncClient(transport=ASGITransport(app))` calls `/api/health`; `asyncio.run` with `wait_for(…, 6)` | `/api/health` answers 200 in under 0.5 s while the handler sleeps; handler called 3 times, blocks in order 812, 832, 838; never more than one concurrent call; handler thread ≠ event loop thread |

If `backend/store.py` is not delivered yet, T3-18, T3-19 and T3-20 (store part) do `pytest.importorskip("backend.store")`.

#### Definition of done

- [ ] With `make seed` run while the engine is running: no alert during setup (`maintenance.flag` file present), window cleared when it disappears.
- [ ] `make test-t3` green (T3-16 as `skip` accepted until T1/T2 are delivered, then green on anvil).
- [ ] `make replay-t3` prints the 8 alerts of T3-10; `make replay-t3 FILE=fixtures/snapshots_normal.jsonl` prints nothing.
- [ ] `make monitor-once` on a seeded anvil prints a valid JSON `Snapshot`.
- [ ] With `ENGINE_ENABLED=true USE_FIXTURES=false make backend` then `make attack` (T2): R1 appears in `/api/alerts` at most 2 polls after the forged mint.
- [ ] Break `RPC_URL` (wrong URL): `/api/health` goes `degraded`, the engine continues on `RPC_FALLBACK_URL`.
- [ ] No file outside "Owned files" modified; any requests go in `docs/contract-requests.md`.

#### Known pitfalls

- Maintenance mode: without it, the liquidity setup by `make seed` / `make reset` (large deposits then bot borrows) triggers R2/R3 like an attack. The file is re-read **on every snapshot** (no cache); its path depends on `settings.DATA_DIR` and `settings.NETWORK` read at call time, otherwise tests cannot redirect it.
- `store.generation`: compare on every `ingest`, not only at startup; T2 calls `store.reset()` during `POST /api/demo/reset` while the loop is running.
- Subscribers: never `handler(...)` directly in `run_forever` (the API would freeze during T4's Fuji transactions) and never one `create_task` per alert (calls would overlap and snapshot order would be lost): a single queue, a single dispatcher, `await asyncio.to_thread`.
- `totals.value_usd` includes `idle_usd`: after pulling back to the vault, the total value stays $1,325,000 (it moves from the positions to the vault) and `at_risk_usd` drops to 0. Do not subtract idle from `at_risk_usd`.
- `window_blocks` counts **snapshots**, not blocks. Do not "fix" it by dividing by the block interval: the T3-10 expectations depend on it.
- Rounding: `backing_ratio_bps` comes as is from the bridge (integer division, 1935); `withdrawable_ratio_bps` is rounded to nearest (6667). Never go through a float for an amount: `int(str)` then divide only for display.
- R2: after the drain, the window holds only zeros (from block 45201876 in the fixtures) → `max == 0` → no alert, the key leaves the latch. This is normal; there is no re-emission afterwards.
- R5 only sees a **transition**: a reserve already frozen when the engine starts raises nothing (accepted in the MVP). The in-memory latch starts empty when the backend restarts: already-emitted alerts may be re-emitted once (accepted, see phase 2).
- `latch.filter` must receive all candidates of the snapshot at once: calling it rule by rule would erase the other rules' keys.
- web3 is synchronous: always `asyncio.to_thread` in `run_forever` (block read, collection, `ingest`, subscribers), otherwise the API freezes while T4 waits for a receipt.
- `getReservesData()` returns tuples: name the fields via the ABI (`struct_to_dict`), not by hard-coded position.
- `chain.py` does not yet contain `token()`, `vault()`, `bridge()`, `oracle()` from 2.4 and `chain.contract()` always uses the primary client: the collector builds its contracts on the `client` it receives.
- `fixtures/deployments.example.json` still uses the `Bridge`/`Oracle` keys: the collector follows 2.3 (`MockBridge`, `MockOracle`).
- Fuji: about 20 RPC calls per snapshot every 2 s; the public RPC is rate-limited, use a provider `RPC_URL`.
- `settings.USE_FIXTURES` read at import = tests cannot switch it: read it in each route.

#### Later (phase 2)

- Advanced rules: spike in deposited collateral (rsETH 900 → 5,900 in 2 blocks), bait yield (abnormal `supply_apy_bps`), contagion between deployments sharing a collateral, oracle vs market price gap, tracing of events (`Released(backed=false)`, `Borrowed`) and of the attacker's funds.
- Multicall3 to read a snapshot in a single RPC call; block-by-block catch-up instead of the head block only.
- Persistent latch (reloaded from `store.alerts()`), hot reload of `rules.yaml`, window in blocks or seconds, per-asset thresholds.
- Internal engine metrics (collection latency, RPC errors) exposed in `/api/health`.

#### Claude Code starter prompt

```
You are working on task T3 (monitoring engine) from the TASKS.md file at the repo root.
1. Read TASKS.md sections 1 and 2 in full, then the T3 section in full. Read backend/models.py,
   backend/settings.py, backend/chain.py, backend/api/state.py and a few lines of
   fixtures/snapshots_attack.jsonl.
2. Modify ONLY: backend/collector.py, backend/rules.py, backend/engine.py,
   backend/config/rules.yaml, backend/api/state.py, backend/tests/test_t3_*.py, mk/t3.mk.
   For any other change (models.py, chain.py, store.py, main.py, fixtures, section 2
   contract), do not edit: write the request in docs/contract-requests.md and tell me.
3. Start with the tests from the "Tests that must pass" section (T3-01 to T3-23), in
   order: rules.yaml, rules.py, engine.py (on the jsonl fixtures, with a local MemStore
   with generation if backend/store.py does not exist; maintenance mode, generation, subscriber
   dispatcher via asyncio.to_thread), api/state.py (totals and risk_level exactly per 2.6,
   503 "no snapshot yet"), then collector.py (anvil test skipped as long as deployments/local.json
   does not exist or the vault has no position).
4. The expected figures (blocks 45201812, 826, 832, 836, 838, 878; exposures 1,325,000 and
   775,000 USD) are measured on the fixtures: if a test does not reproduce them, fix the code,
   not the expectation. Report any real discrepancy to me.
5. Keep the rules simple: one indicator per rule, nothing beyond R1..R5.
6. Before each commit: make test-t3 green (pytest backend/tests/test_t3_*.py, never -k).
   Push often after each green test.
```


---
### T4 · Response and evidence: matrix, on-chain actions, notifications, anchoring, verify

**Goal.** Turn the new alerts of a snapshot into **one** deterministic `Decision` (matrix 2.8), execute the automatic actions (deposit pause, emergency withdrawals to the vault) with the guardian key, notify, then **prove**: evidence file, `inputs_hash`, `record_hash`, anchoring in `EvidenceRegistry`, and a `verify` command an auditor can replay (`MATCH` / `MISMATCH` with the differences).

**Depends on.**
- T0 → `backend/models.py`, `backend/settings.py`, `backend/chain.py`, `backend/store.py`, `main.py` wiring → already there; if `backend/store.py` does not exist yet, use the test `FakeStore` (see 3.9).
- T3 → `Alert` objects (R1..R5) and live `Snapshot` → meanwhile: `Snapshot` read from `fixtures/snapshots_attack.jsonl` and `Alert` built by hand (helper `make_alert`, see 3.9).
- T1 → deployed contracts, `deployments/local.json`, `abi/*.json` → meanwhile: `DRY_RUN_ACTIONS=true` (`DryRunExecutor`, no transaction); later local anvil (`make chain && make deploy`).
- T2 → vault seeded on anvil (`make seed`) → meanwhile: only the dry-run tests run, the anvil test is `skip`.
- T8 → `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET` → meanwhile: empty (log + local files only).

**Unblocks.** T5 (receives `Decision` via `on_decisions`, reads `saved_usd` from the `EMERGENCY_WITHDRAW.amount`), T6 (`GET /api/decisions`, approval button, Verify button), T7 (reads decisions for reaction time and % saved), T9 (`make verify` demo, `tamper` demo for the jury).

**Owned files.** `backend/responder.py`, `backend/executor.py`, `backend/notify.py`, `backend/evidence.py`, `backend/cli.py`, `backend/config/playbook.yaml`, `backend/api/response.py`, `backend/tests/test_t4_*.py`, `mk/t4.mk`. Written at runtime (not committed): `data/evidence/<decision_id>.json`, `data/evidence/anchors.json`.

**Read before starting.** TASKS.md sections 1.2, 1.5, 2.1, 2.2 (`TreasuryVault`, `EvidenceRegistry`, `MiniLend.getUserSupplied/getReservesData`), 2.4, 2.5, 2.6, 2.7, **2.8**, 2.9, **2.10**; `backend/models.py` (`Action`, `Decision`, `VerifyResult`); `backend/chain.py`; 3 lines of `fixtures/snapshots_attack.jsonl` (blocks 45201812, 45201826, 45201838).

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| New alerts of a snapshot | `list[Alert]` (2.6, rule_id `R1_BACKING_DROP`..`R5_RESERVE_FROZEN`) passed to `Responder.handle` | T3 (`engine.on_alerts`) | `make_alert(...)` in `backend/tests/test_t4_fixtures.py`; `fixtures/alerts.json` (regenerated: R1 alert at block 45201812) serves as a format example, not a test input |
| Current snapshot | `Snapshot` (positions, reserves with `ltv_bps`, `vault.deposits_paused`) | T3 (collector) | `load_attack(block)` reading `fixtures/snapshots_attack.jsonl` (network `fuji`, 41 snapshots) |
| Addresses and ABIs | `deployments/<network>.json`, `abi/TreasuryVault.json`, `abi/EvidenceRegistry.json`, `abi/MiniLend.json` | T1 | `DRY_RUN_ACTIONS=true` |
| Keys | `settings.private_key("guardian" / "owner" / "evidence")` via `chain.account(role)` | T0 / `.env` | anvil accounts (index 2, 1, 5) automatic on `local` |
| Store | `store` from `backend/store.py` (2.10) | T0 | `FakeStore` (in-memory lists, same methods) |
| AWS config | `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `AWS_REGION`, `ALERT_WEBHOOK_URL` | T8 / `.env` | empty |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `Decision` | model 2.6; id `DEC-<network>-<block>-<n>` where `<block>` = block of the alerts' snapshot (alert at block N → `DEC-<network>-N-1`); added by `store.add_decision`, updated by `store.update_decision` | T5, T6, T7 |
| Subscriber call | `handler(decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot)` after storage | T5 (`IncidentManager.handle`) |
| Evidence file | `data/evidence/<decision_id>.json` = `{"decision": {...}, "inputs": {"alerts": [...], "snapshot": {...}}, "playbook_yaml": "<text>", "approvals": []}` (UTF-8, indent 2) | `verify`, T9, auditor |
| Dry-run anchors | `data/evidence/anchors.json` = `{"0x<record_hash>": {"tx_hash": "0xdry…", "block_number": int, "kind": "decision", "uri": "…"}}` | `verify` in dry-run |
| S3 copy | `s3://$EVIDENCE_BUCKET/evidence/<decision_id>.json` (same content) if the variable is set | T8, auditor |
| On-chain anchor | `EvidenceRegistry.anchor(record_hash, "decision", uri)` signed by `evidence` | `verify`, T6 (explorer link via `anchor_tx`) |
| Notification | always log; JSON webhook POST; SNS publish | humans, T8 |
| Routes | `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}` (2.9) | T6 |
| CLI | `python -m backend.cli verify <id>` → stdout `MATCH`/`MISMATCH` + diffs, exit 0/1 (2 if unknown id); `tamper`, `restore` | T9, jury |

#### Detailed specification

**3.1 `backend/config/playbook.yaml`** (encodes 2.8, nothing else)

```yaml
version: 1
min_exposure_usd: 1000
matrix:                      # max severity of the group -> actions, in this order
  critical:
    - { type: NOTIFY,             mode: auto }
    - { type: PAUSE_DEPOSITS,     mode: auto }
    - { type: EMERGENCY_WITHDRAW, mode: auto,  per_position: true }
    - { type: OPEN_INCIDENT,      mode: auto }
    - { type: UNPAUSE_DEPOSITS,   mode: human }
  high:
    - { type: NOTIFY,             mode: auto }
    - { type: PAUSE_DEPOSITS,     mode: auto }
    - { type: EMERGENCY_WITHDRAW, mode: human, per_position: true }
    - { type: OPEN_INCIDENT,      mode: auto }
  warning:
    - { type: NOTIFY, mode: auto }
  info: []
below_min_exposure:          # exposure < min_exposure_usd
  notify_if_severity_at_least: high
```

`load_playbook() -> tuple[dict, str, str]` in `responder.py`: reads `settings.CONFIG_DIR / "playbook.yaml"`, returns `(dict, version, text)` with `version = "sha256:" + hashlib.sha256(file_bytes).hexdigest()` (71 characters). Reloaded on every `handle` (editing the file changes `playbook_version`).

**3.2 Pure functions of `backend/responder.py`** (no network, disk, clock or env access)

- `SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}`.
- `deployment_order(snapshot) -> list[str]`: deployment ids in order of first appearance in `snapshot.reserves` (fixtures: `["lend-eth", "lend-avax"]`).
- `concerned_positions(alert, snapshot) -> list[PositionSnapshot]`:
  - `R1_BACKING_DROP`: deployments where a reserve with `asset == alert.asset` has `ltv_bps > 0`; all vault positions in those deployments;
  - `R2_LIQUIDITY_DROP`, `R3_UTILIZATION_HIGH`, `R4_POSITION_STUCK`: the position `(alert.deployment_id, alert.asset)` if it exists;
  - `R5_RESERVE_FROZEN`: all positions of `alert.deployment_id`;
  - unknown rule_id: `[]` + `logger.warning`.
  - Positions with `supplied == "0"` are ignored. Sort: `(index in deployment_order, asset)` → `lend-eth USDC, lend-eth WETH, lend-avax USDC, lend-avax WETH`.
- `assess(alerts, snapshot, playbook) -> dict`: `severity` = max severity; `positions` = union (key `(deployment_id, asset)`, **no duplicates**) of the concerned positions of all alerts with severity ≥ high; `exposure_usd` = sum of `value_usd` over the union of the concerned positions of **all** alerts; `withdrawable_usd` = sum of `withdrawable_usd` over that same union; `matrix_cell = f"{severity}|{'exposure>=1k' if exposure_usd >= min_exposure_usd else 'exposure<1k'}|{'exit_possible' if withdrawable_usd > 0 else 'no_liquidity'}"`. Round floats to 2 decimals.
- `plan_actions(alerts: list[Alert], snapshot: Snapshot, playbook: dict) -> list[Action]` (signature 2.10):
  1. Empty `alerts` → `[]`. Compute `assess`.
  2. If `exposure_usd < min_exposure_usd`: `[Action(NOTIFY, auto, planned)]` if `severity >= notify_if_severity_at_least`, otherwise `[]`.
  3. Otherwise, for each entry of `matrix[severity]`: `status = "planned"` if `mode == "auto"`, `"pending_approval"` if `mode == "human"`; `params = {}`.
     - `PAUSE_DEPOSITS`: always present in the list (keeps verify stable); if `snapshot.vault.deposits_paused` is true → `status="skipped"`, `note="already paused"`.
     - `per_position: true`: one `EMERGENCY_WITHDRAW` per position of `assess.positions` with `int(withdrawable_now) > 0`, `params` = **exactly** `{"deployment_id": ..., "asset": ...}` (nothing else, no amount: the amount goes into `Action.amount`, filled only when the action becomes `executed`). Zero withdrawable positions → no action of this type.
     - `OPEN_INCIDENT`: `params = {}` (T5 assigns the `INC-…` id; T4 never writes it anywhere in the decision). `NOTIFY`, `PAUSE_DEPOSITS`, `UNPAUSE_DEPOSITS`: `params = {}` too.
  4. `amount`, `tx_hash`, `executed_at` stay `None`. Never mutate the received objects (use `model_copy`).
- `rationale(decision_fields) -> str`, fixed English template: `"{severity} alert(s) {rule_ids} with ${exposure_usd:,.0f} exposed: {n_auto} automatic action(s), {n_human} awaiting approval."` (`rule_ids` sorted, separated by `", "`).

**3.3 `backend/executor.py`**

```python
class ExecResult(TypedDict):
    status: Literal["executed", "failed", "skipped"]
    tx_hash: str | None; block_number: int | None; amount: str | None; note: str | None

class Executor(Protocol):
    def pause_deposits(self) -> ExecResult: ...
    def unpause_deposits(self) -> ExecResult: ...
    def emergency_withdraw(self, deployment_id: str, asset: str) -> ExecResult: ...
    def anchor(self, record_hash: str, kind: str, uri: str) -> ExecResult: ...

def make_executor() -> Executor      # DryRunExecutor if settings.DRY_RUN_ACTIONS, otherwise Web3Executor
def get_executor() -> Executor       # singleton (2.10, functools.lru_cache): DryRunExecutor if DRY_RUN_ACTIONS=true, otherwise Web3Executor;
                                     # shared by Responder (main.py: Responder(store, get_executor())) and api/response.py;
                                     # tests call get_executor.cache_clear() after monkeypatching DRY_RUN_ACTIONS
```

- **No method raises**: any exception → `{"status": "failed", "note": f"{type(e).__name__}: {e}"[:200]}` + `logger.exception`.
- `Web3Executor` (contracts via `chain.vault()`, `chain.lending(id)`, `chain.registry()` from 2.4; if these helpers are still missing in `chain.py`, `chain.contract("TreasuryVault")` / `chain.contract("EvidenceRegistry")`):
  - `pause_deposits`: if `vault.functions.depositsPaused().call()` → `skipped`, `"already paused"`; otherwise `chain.send(vault.functions.pauseDeposits(), chain.account("guardian"))` (`pauseDeposits` is idempotent on the contract side, the pre-check only avoids spending gas). Receipt `status` 0 → `failed`, `"reverted"`.
  - **Revert reason**: before each `chain.send`, simulate the call with `fn.call({"from": sender.address})`; a `ContractLogicError` → `failed`, `note` = revert message (e.g. `"MiniLend: paused"`, `"Vault: only guardian or owner"`), without sending the transaction. Same handling if `chain.send` raises a `ContractLogicError` (gas estimation).
  - `unpause_deposits`: **owner** key (`unpauseDeposits` is owner-only); not paused → `skipped`, `"not paused"`.
  - `emergency_withdraw(dep, asset)`: `asset_addr = chain.load_deployment()["assets"][asset]`; `supplied = lending(dep).functions.getUserSupplied(vault.address, asset_addr).call()`; `0` → `skipped`, `"no position left"`; liquidity = `availableLiquidity` of the `getReservesData()` entry whose `asset == asset_addr`; `0` → `skipped`, `"no liquidity"` (the contract would return 0 without reverting, no point paying gas); otherwise `send(vault.functions.emergencyWithdraw(lending(dep).address, asset_addr), guardian)`; `amount` = `amount` field of the receipt's `EmergencyWithdrawal` event (`vault.events.EmergencyWithdrawal().process_receipt(w3().eth.get_transaction_receipt(tx))`), falling back to `min(supplied, liquidity)`, as a decimal string. Paused reserve (`setReservePaused`): `emergencyWithdraw` reverts `"MiniLend: paused"` → the action becomes `failed` with `note="MiniLend: paused"` (the revert reason, not `"reverted"`); the following actions continue.
  - `anchor(record_hash, kind, uri)`: `h = bytes.fromhex(record_hash[2:])`; if `registry.functions.anchoredAt(h).call() > 0` → `skipped`, `"already anchored"`, `block_number` = that value; otherwise `send(registry.functions.anchor(h, kind, uri), chain.account("evidence"))`.
- `DryRunExecutor`: no transaction, but a small state for idempotence: `paused: bool = False`, `withdrawn: set[tuple[str, str]]`, `seq: int = 0`. Fake hash: `"0xdry" + hashlib.sha256(f"{method}|{json.dumps(args)}|{seq}".encode()).hexdigest()` (69 characters, deterministic for a fresh instance). `block_number` = `seq`. `pause_deposits` twice → 2nd `skipped "already paused"`; `emergency_withdraw` twice on the same pair → 2nd `skipped "no position left"`; `amount=None` (the Responder fills it with `withdrawable_now`). `anchor` writes/extends `data/evidence/anchors.json` (`skipped "already anchored"` if the key exists).

**3.4 `backend/notify.py`**

`notify(decision: Decision, alerts: list[Alert]) -> list[str]`: returns the **configured** channels (`["log"]`, + `"webhook"` if `ALERT_WEBHOOK_URL`, + `"sns"` if `SNS_TOPIC_ARN`). Always `logger.warning("NOTIFY %s %s exposure=$%.0f %s", decision.id, decision.severity, decision.exposure_usd, decision.rationale)`. Webhook and SNS go out in a `threading.Thread(daemon=True)` so they do not delay the emergency withdrawal. JSON body: `{"text": summary, "content": summary, "decision_id", "severity", "network", "block_number", "exposure_usd", "matrix_cell", "alerts": [{"id","rule_id","severity","explanation"}], "actions": [{"type","mode","status"}]}` (`text` for Slack, `content` for Discord). `httpx.post(url, json=..., timeout=3)`. SNS: `boto3.client("sns", region_name=settings.AWS_REGION).publish(TopicArn=..., Subject=f"[{severity.upper()}] {decision.id}"[:100], Message=json.dumps(body))`. Every exception is logged and swallowed. Testable internal function `build_payload(decision, alerts) -> dict`.

**3.5 `backend/evidence.py`**

```python
EVIDENCE_DIR: Path = settings.DATA_DIR / "evidence"          # tests monkeypatch it to tmp_path
def canonical_json(obj) -> str            # BaseModel -> model_dump(mode="json"); lists of BaseModel likewise; then
                                          # json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def keccak_hex(text: str) -> str          # "0x" + eth_utils.keccak(text.encode("utf-8")).hex()  (66 characters)
def inputs_hash(alerts, snapshot) -> str  # keccak_hex(canonical_json({"alerts": [a sorted by id], "snapshot": snapshot}))
def record_hash(decision) -> str          # keccak_hex(canonical_json(decision.model_dump(mode="json",
                                          #   exclude={"record_hash", "anchor_tx", "anchor_block"})))
def evidence_uri(decision_id) -> str      # f"s3://{EVIDENCE_BUCKET}/evidence/{id}.json" if bucket, otherwise f"file://data/evidence/{id}.json"
def write_evidence(decision, alerts, snapshot, playbook_yaml) -> Path   # writes the file, then S3 upload if bucket (failure logged, never raised)
def anchor_decision(decision, executor) -> Decision                      # executor.anchor(record_hash, "decision", uri) -> anchor_tx, anchor_block
def load_evidence(decision_id) -> dict | None                            # local, otherwise S3 if bucket, otherwise None
def verify(decision_id) -> VerifyResult
```

`verify` (uses **only** the evidence file, never the store, because approvals modify the live decision):
1. `ev = load_evidence(id)`; missing → `LookupError` (API → 404, CLI → exit 2).
2. `d = Decision.model_validate(ev["decision"])`, `alerts`, `snapshot` from `ev["inputs"]`.
3. Recomputed `inputs_hash` ≠ `d.inputs_hash` → diff `"inputs_hash: stored 0x… != recomputed 0x…"`.
4. Playbook: `ev["playbook_yaml"]`; its sha256 ≠ `d.playbook_version` → diff `"playbook_version: …"`. Re-plan `plan_actions(alerts, snapshot, yaml.safe_load(playbook_yaml))` and compare `(type, mode, params)` index by index: `"action count: stored 8 != replanned 7"`, `"action[2]: stored EMERGENCY_WITHDRAW/auto {'asset': 'DAI', ...} != replanned EMERGENCY_WITHDRAW/auto {'asset': 'USDC', ...}"`.
5. `recomputed_hash = record_hash(d)`; ≠ `d.record_hash` → diff `"record_hash: …"`.
6. Anchoring: if `d.anchor_tx` starts with `"0xdry"` → `anchors.json` contains `d.record_hash`; otherwise `registry.functions.anchoredAt(bytes.fromhex(d.record_hash[2:])).call() > 0` (RPC error → `anchored=False`, diff `"registry unreachable: …"`). If `d.anchor_tx` is set and not anchored → diff `"record_hash 0x… is not anchored on-chain"`.
7. `match = (diffs == [])`. `VerifyResult(decision_id, match, stored_hash=d.record_hash, recomputed_hash, anchored, anchor_tx, anchor_block, diffs)`.

**3.6 `Responder` (`backend/responder.py`)**

`__init__(self, store, executor)`: keeps `self._handlers = []`, `self._seen_alert_ids: set[str]` (initialized from `store.decisions()`) and `self._generation = store.generation`; at the start of `handle`, if `store.generation` changed (demo reset), clear `_seen_alert_ids` and remember the new generation. `handle` is called by the engine via `await asyncio.to_thread(handler, alerts, snapshot)`, one call at a time in snapshot order (2.10): no lock to add, but `handle` runs outside the asyncio loop (no `await` inside). `on_decisions(handler)` adds a subscriber. `handle(alerts, snapshot) -> list[Decision]`, **never raises** (global try/except → `logger.exception`, returns `[]`):
1. Filter out already-seen alerts (`id in _seen_alert_ids`); nothing new → `[]`.
2. `playbook, version, text = load_playbook()`; `actions = plan_actions(...)`; `actions == []` → `[]` (no decision for `info`).
3. `n = 1 + number of store decisions with this block_number` → `id = f"DEC-{snapshot.network}-{snapshot.block_number}-{n}"`: the block is that of the **alerts' snapshot** (= `alert.block_number`), never the transactions' execution block nor the anchoring block. R1 alert at block 45,201,812 → `DEC-fuji-45201812-1` (as in the regenerated fixtures). `created_at = datetime.now(timezone.utc).replace(microsecond=0)`. `rules_version` = that of the 1st alert. `exit_cost_bps = 0`.
4. Execute in order, only `mode == "auto"` and `status == "planned"`: `NOTIFY` → `notify(...)`, `status="executed"`, `note="channels: log,webhook"` (**never** touch `params`); `PAUSE_DEPOSITS` → `executor.pause_deposits()`; `EMERGENCY_WITHDRAW` → `executor.emergency_withdraw(dep, asset)`, `amount = result.amount or position.withdrawable_now` if `executed`; `OPEN_INCIDENT` → `status="executed"`, `note="delegated to incident manager"`, `params` stays `{}`. Copy `status`, `tx_hash`, `amount`, `note`, `executed_at=now` from the `ExecResult`. A failure does not stop the following actions.
5. `inputs_hash`, `rationale`, then `record_hash`; `write_evidence`; `anchor_decision` (failure → `anchor_tx=None`, log); rewrite the file with the anchoring fields; `store.add_decision(d)`; mark the alerts as seen.
6. Logs: `DECISION DEC-fuji-45201812-1 critical exposure=$1,325,000 cell=critical|exposure>=1k|exit_possible actions=NOTIFY,PAUSE_DEPOSITS,EMERGENCY_WITHDRAWx4,OPEN_INCIDENT,UNPAUSE_DEPOSITS(pending)` then one line `ACTION <type> <params> <status> tx=<hash> amount=<amount>` per action.
7. Call each handler `(decisions, alerts, snapshot)` in a separate try/except; return `[d]`.

**3.7 `backend/api/response.py`** (T4 routes from 2.9; read `settings.USE_FIXTURES` **on every request**, not at import)
- `GET /decisions`: fixtures → `decisions.json`; otherwise `store.decisions()` (most recent first).
- `POST /decisions/{id}/approve` body `ApproveBody`; contract error codes (2.9), always `{"detail": "..."}`: unknown id → 404; `action_index` out of bounds → 400; action not in `pending_approval` → 409 `{"detail": "action is not pending approval (status=executed)"}`; invalid body → 422 (FastAPI). `approve=false` → `rejected`, `note=f"rejected by {approver}; no transaction sent"`. `approve=true` → `approved` then execution via `get_executor()` (`EMERGENCY_WITHDRAW` → `emergency_withdraw`, `UNPAUSE_DEPOSITS` → `unpause_deposits`, `PAUSE_DEPOSITS` → `pause_deposits`) → `executed`/`failed`/`skipped`, `note=f"approved by {approver}; {result.note or ''}"`. **`note` format documented for T5** (which reads it for the incident timeline): always `"approved by <approver>; <detail>"` or `"rejected by <approver>; <detail>"`; T5 extracts the approver with `note.split(";")[0].split(" by ", 1)[1]`. An approved `EMERGENCY_WITHDRAW` that reverts `"MiniLend: paused"` → `failed`, `note="approved by <approver>; MiniLend: paused"`. In dry-run `amount` is `None`: fill it with the position's `withdrawable_now` from `ev["inputs"]["snapshot"]`. `store.update_decision(d)` and append to `ev["approvals"]` `{"action_index", "approver", "approve", "at", "result": action.model_dump(mode="json")}`. The `record_hash` is **not** recomputed (it freezes the state at decision time).
- `POST /verify/{decision_id}`: fixtures → `verify.json` with `decision_id` replaced; otherwise `evidence.verify` (LookupError → 404).

**3.8 `backend/cli.py` and `mk/t4.mk`**

`main(argv: list[str] | None = None) -> int` (testable without subprocess), `argparse`:
- `verify <id>`: 1st line `MATCH` or `MISMATCH`, then `decision: …`, `record_hash: …`, `anchored: yes (block 123, tx 0x…)` + `chain.explorer_tx` link if fuji, then one line `- <diff>` per diff. Exit 0 if match, 1 otherwise, 2 if unknown id.
- `tamper <id> --field <path> --value <v>`: dotted path into the evidence file (`decision.actions.2.params.asset`, `inputs.snapshot.positions.1.withdrawable_now`); integers = list indexes; `v` parsed with `json.loads`, otherwise a string. Saves `data/evidence/<id>.json.bak` before editing (without overwriting an existing `.bak`). Prints `TAMPERED <path>: <old> -> <new>`.
- `restore <id>`: puts the `.bak` back.

```make
verify:  ; python -m backend.cli verify $(ID)
tamper:  ; python -m backend.cli tamper $(ID) --field $(FIELD) --value '$(VALUE)'
restore: ; python -m backend.cli restore $(ID)
test-t4: ; DRY_RUN_ACTIONS=true USE_FIXTURES=false python -m pytest backend/tests/test_t4_*.py -q
```

**3.9 Test mocks (`backend/tests/test_t4_fixtures.py`, no tests, imported by the others)**: `load_attack(block) -> Snapshot`; `make_alert(rule_id, severity, snapshot, deployment_id=None, asset=None, exposure_usd=...) -> Alert` (id in 2.5 format, `rules_version="sha256:test"`); `FakeStore` (2.10 methods in memory); pytest fixture `evidence_tmp` that monkeypatches `backend.evidence.EVIDENCE_DIR` to `tmp_path`.

#### Tests that must pass

Command: `make test-t4` (= `python -m pytest backend/tests/test_t4_*.py -q`, never `-k`). All in dry-run except T4-25.

| Id | File::test | Setup | Expected result |
|---|---|---|---|
| T4-01 | `test_t4_plan.py::test_playbook_loads` | real file | `min_exposure_usd == 1000`; version starts with `sha256:`, length 71 |
| T4-02 | `test_t4_plan.py::test_plan_r1_critical_attack` | `load_attack(45201812)` + R1 critical `rsETH` (exposure 1325000) | 8 actions, exactly: `NOTIFY/auto/planned`, `PAUSE_DEPOSITS/auto/planned`, `EMERGENCY_WITHDRAW/auto/planned` ×4 with params `{lend-eth,USDC}`, `{lend-eth,WETH}`, `{lend-avax,USDC}`, `{lend-avax,WETH}`, `OPEN_INCIDENT/auto/planned`, `UNPAUSE_DEPOSITS/human/pending_approval`; `assess`: `exposure_usd == 1325000.0`, `withdrawable_usd == 1325000.0`, `matrix_cell == "critical|exposure>=1k|exit_possible"` |
| T4-03 | `test_t4_plan.py::test_plan_r2_high` | `load_attack(45201826)` + R2 high `lend-eth/WETH` | `NOTIFY`, `PAUSE_DEPOSITS(auto, planned)`, `EMERGENCY_WITHDRAW(human, pending_approval, {lend-eth, WETH})`, `OPEN_INCIDENT`; exposure 375000.0 |
| T4-04 | `test_t4_plan.py::test_plan_warning_notify_only` | `load_attack(45201836)` + R3 warning `lend-eth/WETH` | `[NOTIFY/auto/planned]` |
| T4-05 | `test_t4_plan.py::test_plan_below_min_exposure` | snapshot 45201836 whose `lend-eth/WETH` position has `value_usd=500`; R4 high then R4 critical | `[NOTIFY]` in both cases; cell `high|exposure<1k|exit_possible` |
| T4-06 | `test_t4_plan.py::test_plan_info_empty` | R5 forced to `info` | `[]` |
| T4-07 | `test_t4_plan.py::test_plan_critical_no_liquidity` | `load_attack(45201838)` + R4 critical `lend-eth/WETH` (ratio 0) | `NOTIFY, PAUSE_DEPOSITS, OPEN_INCIDENT, UNPAUSE_DEPOSITS(human)` (no `EMERGENCY_WITHDRAW`); cell `critical|exposure>=1k|no_liquidity` |
| T4-08 | `test_t4_plan.py::test_plan_already_paused` | snapshot 45201812 with `vault.deposits_paused=True` | `PAUSE_DEPOSITS` present, `status=="skipped"`, `note=="already paused"` |
| T4-09 | `test_t4_plan.py::test_plan_group_no_double_count` | 45201812: R1 critical + R2 high `lend-eth/WETH` | 1 critical group, exposure 1325000.0 (not 1700000), 4 `EMERGENCY_WITHDRAW` |
| T4-10 | `test_t4_plan.py::test_plan_is_pure` | 2 identical calls | equal outputs; `snapshot.model_dump()` unchanged |
| T4-11 | `test_t4_evidence.py::test_canonical_json` | — | `canonical_json({"b":1,"a":2}) == '{"a":2,"b":1}'`; `canonical_json({"x":"é"}) == '{"x":"é"}'`; `keccak_hex("") == "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"` |
| T4-12 | `test_t4_evidence.py::test_hash_roundtrip` | decision from T4-16 | `record_hash(Decision.model_validate_json(d.model_dump_json())) == d.record_hash`; `inputs_hash` identical across 2 calls and for alerts passed in reverse order |
| T4-13 | `test_t4_evidence.py::test_record_hash_scope` | same | changing `anchor_tx` → hash unchanged; changing `actions[0].note` → hash different |
| T4-14 | `test_t4_executor.py::test_dry_run_hash` | 2 fresh `DryRunExecutor` | `pause_deposits()["tx_hash"]` starts with `0xdry`, length 69, identical between the 2 instances |
| T4-15 | `test_t4_executor.py::test_dry_run_idempotent` | 1 instance | 2nd pause → `skipped "already paused"`; 2nd withdrawal `lend-eth/USDC` → `skipped "no position left"` |
| T4-16 | `test_t4_responder.py::test_handle_critical` | `FakeStore`, `DryRunExecutor`, `evidence_tmp`, R1 on 45201812, spy handler | returns 1 decision `DEC-fuji-45201812-1`; statuses: NOTIFY `executed`, PAUSE `executed`, 4 EW `executed` with `amount` `"400000000000"`, `"150000000000000000000"`, `"300000000000"`, `"100000000000000000000"`, OPEN_INCIDENT `executed`, UNPAUSE `pending_approval`; `record_hash` 66 chars; `anchor_tx` starts with `0xdry`; `anchor_block > 0`; `evidence_tmp/DEC-fuji-45201812-1.json` exists; handler called once |
| T4-17 | `test_t4_responder.py::test_handle_idempotent` | replay T4-16; then R4 critical on 45201838 with `deposits_paused=True` | identical 2nd call → `[]`, store = 1 decision; next decision `DEC-fuji-45201838-1` with PAUSE `skipped "already paused"` and 0 EW |
| T4-18 | `test_t4_responder.py::test_handle_survives_failures` | executor whose `emergency_withdraw` raises `RuntimeError("boom")` | no exception; 4 EW `failed` with `note` containing `boom`; OPEN_INCIDENT `executed`; decision stored |
| T4-19 | `test_t4_notify.py::test_notify_never_raises` | `ALERT_WEBHOOK_URL=http://127.0.0.1:9`, bogus `SNS_TOPIC_ARN`, `boto3.client` monkeypatched to raise | no exception; returns `["log", "webhook", "sns"]` |
| T4-20 | `test_t4_notify.py::test_payload` | T4-16 decision | `build_payload` has keys `text`, `content`, `decision_id`, `severity=="critical"`, 1 alert |
| T4-21 | `test_t4_verify.py::test_verify_match` | T4-16 decision | `match is True`, `diffs == []`, `anchored is True`, `stored_hash == recomputed_hash` |
| T4-22 | `test_t4_verify.py::test_verify_tamper` | `cli.main(["tamper", id, "--field", "decision.actions.2.params.asset", "--value", "DAI"])` then `cli.main(["verify", id])`; then `restore`, then tamper `inputs.snapshot.positions.1.withdrawable_now` = `"0"` | 1st: exit 1, stdout starts with `MISMATCH`, diffs contain `record_hash` and `action[2]`; after `restore`: exit 0, `MATCH`; 2nd tamper: diffs contain `inputs_hash` and `action count: stored 8 != replanned 7` |
| T4-23 | `test_t4_verify.py::test_verify_not_anchored` | remove the entry from `anchors.json` | `anchored False`, `match False`, diff contains `not anchored`; `cli.main(["verify", "DEC-x"])` → 2 |
| T4-24 | `test_t4_api.py::test_routes` | `TestClient(app)`, `USE_FIXTURES` monkeypatched, `FakeStore` + `DryRunExecutor` injected | fixtures: `GET /api/decisions` = length of `decisions.json`; live: R2 high decision from T4-03 created via `Responder.handle` (evidence written, id `DEC-fuji-45201826-1`), `POST /api/decisions/<id>/approve {"action_index":2,"approver":"risk-officer","approve":true}` → 200, `actions[2].status=="executed"`, `amount=="150000000000000000000"`, `note` starts with `approved by risk-officer`; same POST → 409; index 0 → 409; index 9 → 400; unknown id → 404; body without `approver` → 422; on a 2nd decision, `approve:false` → `rejected`, `note` starts with `rejected by risk-officer;`; `POST /api/verify/<id>` → `match true`; verify unknown id → 404 |
| T4-25 | `test_t4_anvil.py::test_critical_on_anvil` (skip if RPC unreachable, `deployments/local.json` missing or vault empty) | `make chain && make deploy && make seed`; `DRY_RUN_ACTIONS=false`; snapshot built from the chain by the test (positions via `getUserSupplied`, reserves via `getReservesData`); R1 critical by hand; `Web3Executor` | `vault.depositsPaused() is True`; `USDC.balanceOf(vault)` +700000000000 and `WETH.balanceOf(vault)` +250000000000000000000; 4 EW `executed` with `tx_hash` 0x 66 chars; `registry.anchoredAt(record_hash) > 0`; `subprocess.run(["make","verify",f"ID={id}"])` → code 0, output contains `MATCH`; approval of `UNPAUSE_DEPOSITS` via the API → `depositsPaused() is False` |

#### Definition of done

- [ ] `make test-t4` green in dry-run with no chain or AWS (T4-25 skip).
- [ ] T4-25 green on anvil after `make chain deploy seed`.
- [ ] `plan_actions` pure, reused as is by `verify`.
- [ ] A single `Decision` per snapshot, idempotent, never an exception propagated to the engine.
- [ ] `data/evidence/<id>.json` written and anchored for every decision; `make verify ID=…` → `MATCH`; `make tamper` → readable `MISMATCH`.
- [ ] T4 routes from 2.9 working in fixtures and live; T6 front can approve an `EMERGENCY_WITHDRAW` and an `UNPAUSE_DEPOSITS`.
- [ ] No key in the code; `GUARDIAN_PK` used only for pause and emergency withdrawal.
- [ ] Fuji demo: one anchored decision, snowtrace link of `anchor_tx` opened by hand.

#### Known pitfalls

- **Unstable hash**: always `model_dump(mode="json")` before `canonical_json`; datetimes in UTC with timezone (otherwise `+00:00` vs `Z`); never rewrite a float afterwards; sort alerts by id.
- **`.hex()`**: depending on the `hexbytes` version, `HexBytes.hex()` includes `0x` or not. Use `"0x" + bytes(x).hex()` or `Web3.to_hex`.
- **`params` modified after planning** = systematic `MISMATCH` on verify. Results go into `status/tx_hash/amount/note`, never into `params`.
- **Deployment order**: `lend-eth` before `lend-avax` (snapshot order), not alphabetical order.
- **`unpauseDeposits` is owner-only**: calling it with the guardian key reverts.
- **`Evidence: already anchored`**: check `anchoredAt` before sending (re-run, restart).
- **Fuji latency**: ~2 s per transaction, 6 transactions in series ≈ 12 s; `handle` runs in a thread (`asyncio.to_thread`, 2.10) so the API and dashboard stay responsive, but the next snapshot is only processed afterwards (acceptable for the MVP, see phase 2). Webhook/SNS must never delay the withdrawals (thread).
- **Maintenance mode** (2.10): during `seed`/`reset`, the engine evaluates no rules, so `handle` is not called; after a reset, `store.generation` changes and the Responder clears its seen alerts (3.6).
- **Paused reserve**: `emergencyWithdraw` reverts `"MiniLend: paused"`; the action is `failed` with that reason in `note`, never an exception propagated.
- **Nonces**: one key per role and always `chain.send` (per-sender lock); do not sign with `evidence` and `guardian` from another process in parallel.
- **`settings` read at import**: in tests, monkeypatch `backend.settings.X` and read `settings.X` at call time.
- **API fixtures** (`alerts.json`, `decisions.json`, `verify.json`): regenerated (R1 and `DEC-fuji-45201812-1` at block 45,201,812); if your local copy still shows ids `D1..D7`, rebase. For numeric test expectations, only `snapshots_*.jsonl` are authoritative.
- **`tx_hash` `0xdry…`**: 69 characters, not a real hash; the front must not turn it into an explorer link.

#### Later (phase 2)

- Also anchor each human approval (new `record_hash` chained to the previous one) and the rules state (`kind="rules"`).
- Send withdrawals in parallel (threads) and prioritize by risk (drained asset first) instead of the fixed order.
- `FULL_EXIT`, real exit cost (`exit_cost_bps`), multiple exposure thresholds in the matrix.
- Automatic failover to `RPC_FALLBACK_URL` in `Web3Executor`.
- Verify via S3 with Object Lock, signing of evidence files.
- Replay `verify` on the front for all decisions and show the approval history.

#### Claude Code starter prompt

```
You are working on task T4 (response and evidence) of the TASKS.md file at the repo root.
1. Read TASKS.md sections 1 and 2 in full, then the T4 section in full. Read backend/models.py,
   backend/settings.py, backend/chain.py and 3 lines of fixtures/snapshots_attack.jsonl
   (blocks 45201812, 45201826, 45201838). The numeric test expectations come from
   snapshots_attack.jsonl, not from fixtures/alerts.json or decisions.json (format examples).
2. Modify ONLY: backend/responder.py, backend/executor.py, backend/notify.py,
   backend/evidence.py, backend/cli.py, backend/config/playbook.yaml, backend/api/response.py,
   backend/tests/test_t4_*.py, mk/t4.mk. If you need a change elsewhere (models.py,
   chain.py, store.py, main.py, fixtures) or in the section 2 contract, do not edit:
   write the request in docs/contract-requests.md and tell me.
3. Work with DRY_RUN_ACTIONS=true, hand-built Alerts (make_alert helper),
   the Snapshots from fixtures/snapshots_attack.jsonl and a FakeStore if backend/store.py is missing.
   The anvil test (T4-25) must skip cleanly as long as the chain is not there.
4. Start by writing backend/tests/test_t4_fixtures.py then tests T4-01 to T4-25
   (exact names and values from the T4 section), check that they fail, then implement in
   this order: playbook.yaml, plan_actions/assess, evidence, executor, notify, Responder,
   cli, api/response.py, mk/t4.mk.
5. Before each commit: make test-t4 (pytest backend/tests/test_t4_*.py) must be green.
   Small commits, push often after each green test.
```


---
### T5 · Incident and DORA: opening, timeline, classification, report, dependencies

**Goal.** Turn T4's decisions into **a tracked incident** (status, timeline, amounts saved and still at risk), propose its **DORA classification** exactly per RTS (EU) 2024/1772 (Art. 8 and 9), compute the **deadlines** of Regulation (EU) 2025/301, produce the **initial notification draft** (markdown, description optionally drafted by Bedrock) and maintain the **third-party dependency register**. The classification is a **proposal**: only a human submits it (`POST /api/incidents/{id}/submit`).

**Depends on.**
- T0 → `backend/store.py`, `backend/models.py`, stubs, `fixtures/` → if `store.py` is not merged yet: `FakeStore` in `backend/tests/test_t5_factories.py` (same methods as 2.10, in memory, including the `generation` attribute incremented by `reset`).
- T3 → stored `Alert` and `Snapshot` → `fixtures/snapshots_attack.jsonl` (no reaction) + "with reaction" series built by `make_reacted_series()`; alerts built by hand (`make_alert_r1()`).
- T4 → `Decision` (executed actions, `tx_hash`, `amount`), human approvals via `store.update_decision` → decisions built by hand per 2.8 (`make_decision_r1()`), direct mutation of the `FakeStore` to simulate an approval. No transactions: T5 never sends any.
- T8 → Bedrock access (`BEDROCK_MODEL_ID`, AWS credentials) → empty `BEDROCK_MODEL_ID` = deterministic fallback; boto3 client replaced by a stub in tests.

**Unblocks.** T6 (incident page, timeline, DORA badge, deadlines, Submit button, dependencies table), T7 (`saved_usd` / `at_risk_usd` per run), T9 (sample DORA report, compliance sheet), T0 (regeneration of `incident.json` and `dependencies.json` with the real numbers).

**Owned files.** `backend/incidents.py`, `backend/dora.py`, `backend/llm.py`, `backend/config/dora_profile.yaml`, `backend/config/dependencies.yaml`, `backend/api/incidents.py`, `mk/t5.mk`, `backend/tests/test_t5_*.py`.

**Read before starting.** `TASKS.md` sections 1.2, 1.5, 2.5, 2.6, 2.7 (exposure), 2.8 (concerned positions), 2.9 (T5 routes), 2.10 (`IncidentManager`), 2.13; `backend/models.py` (`Incident`, `TimelineEvent`, `DoraCriteria`, `DoraDeadlines`, `DoraAssessment`, `Dependency`); `fixtures/incident.json` and `fixtures/dependencies.json` for the **shape** (the numeric test expectations are computed by our factories, not read from the fixtures).

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| `decisions, alerts, snapshot` passed to `IncidentManager.handle` | `list[Decision]`, `list[Alert]`, `Snapshot` | T4 via `responder.on_decisions` (T0 wiring) | direct call in tests with `make_decision_r1()`, `make_alert_r1()` |
| Snapshot history | `store.snapshots(limit=500)`, `store.latest_snapshot()` | T3 (engine) | `FakeStore` filled with `snapshots_attack.jsonl` or `make_reacted_series()` |
| Up-to-date action status (approvals, human executions) | `store.get_decision(id)` | T4 (`POST /api/decisions/{id}/approve` → `update_decision`) | modify the decision in the `FakeStore` then `manager.refresh(incident_id)` |
| Entity DORA profile | `backend/config/dora_profile.yaml` | T5 | — |
| Third-party register | `backend/config/dependencies.yaml` | T5 | — |
| AI drafting | Bedrock Converse (`BEDROCK_MODEL_ID`, `AWS_REGION`) | T8 (access), T5 (code) | empty variable → template; client stub |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| Current incident | `Incident` written by `store.upsert_incident` on every change | T6, T7, T9 |
| `GET /api/incidents` | `Incident[]`, most recent first (`opened_at` descending) | T6 |
| `GET /api/incidents/{id}` | `Incident`; 404 `{"detail": "incident not found"}` | T6 |
| `GET /api/incidents/{id}/report.md` | `text/markdown; charset=utf-8`, content of `dora.report_markdown` | T6 (link), T9 |
| `POST /api/incidents/{id}/submit` | body `{"submitted_by": str}` → `Incident` with `dora.submitted = true`; 409 if already submitted or no DORA | T6 |
| `GET /api/dependencies` | `Dependency[]` (YAML order) | T6 |
| Report on disk | `data/reports/<INC-id>.md` via `make dora-report ID=…` | T9 |
| Logs | logger `t5.incidents` / `t5.dora` / `t5.llm`, one `key=value` line per event | all (debug) |

#### Detailed specification

**1. DORA profile (`backend/config/dora_profile.yaml`)** — synthetic data, never a real entity:
```yaml
version: 1
entity_name: "Example Treasury SAS (synthetic)"
entity_type: "crypto-asset service provider"
clients_count: 1200
client_member_states: [FR, DE]
critical_services: ["on-chain treasury management"]
usd_to_eur: 0.92
reputational_impact: false
data_losses: false
malicious_unauthorised_access: false   # the flaw is in the third-party bridge, not in our systems (Art. 9(5)(b) targets our IT systems)
```
`load_profile(path: Path = settings.CONFIG_DIR / "dora_profile.yaml") -> dict`: `yaml.safe_load`, checks every key is present, otherwise raises `ValueError("dora_profile: missing <key>")`.

**2. `backend/dora.py`: pure classification (no I/O outside `load_profile`).**
```python
T_9_1  = "9(1) clients, financial counterparts and transactions"
T_9_2  = "9(2) reputational impact"
T_9_3  = "9(3) duration and service downtime"
T_9_4  = "9(4) geographical spread"
T_9_5A = "9(5)(a) data losses"
T_9_5B = "9(5)(b) malicious unauthorised access"
T_9_6  = "9(6) economic impact"
class Classification(NamedTuple): thresholds_met: list[str]; is_major: bool; legal_basis: str
def classify(c: DoraCriteria) -> Classification
```
Thresholds (**strict** ">" comparisons, except 9(4)):
- 9(1) met if any of: `clients_affected_pct > 10`; `clients_affected_count > 100_000`; `counterparts_affected_pct > 30`; `transactions_affected_value_pct > 10`; `transactions_affected_count_pct > 10`; `relevant_clients_affected`. The three optional fields `counterparts_affected_pct`, `transactions_affected_count_pct` and `relevant_clients_affected` exist in `models.py` (2.6, defaults `0` / `0` / `false`): read them directly (`c.counterparts_affected_pct`, etc.).
- 9(2) `reputational_impact`; 9(3) `duration_hours > 24` or `critical_service_downtime_hours > 2`; 9(4) `member_states_affected >= 2`; 9(5)(a) `data_losses`; 9(5)(b) `malicious_unauthorised_access`; 9(6) `economic_impact_eur > 100_000`.
- `thresholds_met` in the article order above. A criterion counts **once** even if several sub-thresholds are met (9(5)(a) and 9(5)(b) count as a single "9(5)" criterion for the two-criteria rule).

Art. 8(1): `is_major = critical_services_affected and (T_9_5B in met or nb_criteres_distincts >= 2)`. `legal_basis` (one sentence, exactly these templates):
- `"RTS (EU) 2024/1772 Art. 8(1)(a): critical services affected and malicious unauthorised access (Art. 9(5)(b)) identified."`
- `"RTS (EU) 2024/1772 Art. 8(1)(b): critical services affected and 2 materiality thresholds of Art. 9 met (9(1), 9(4))."` (count and short list computed)
- `"RTS (EU) 2024/1772 Art. 8(1): not major, no critical service affected."`
- `"RTS (EU) 2024/1772 Art. 8(1): not major, critical services affected but only 1 materiality threshold of Art. 9 met (9(1))."` (or `0 ... met (none)`).

**3. Facts → criteria.**
```python
@dataclass(frozen=True)
class IncidentFacts:
    exposure_usd: float; total_treasury_usd: float; at_risk_usd: float
    aware_at: datetime; end_at: datetime; deposits_paused_hours: float
def compute_criteria(f: IncidentFacts, profile: dict) -> DoraCriteria
```
- `critical_services_affected = bool(profile["critical_services"]) and f.exposure_usd > 0`.
- `clients_affected_pct = round(min(100.0, f.exposure_usd / f.total_treasury_usd * 100), 2)` (0 if total = 0); `clients_affected_count = round(clients_count * pct / 100)`.
- `transactions_affected_value_pct = 0.0`, `counterparts_affected_pct = 0.0`, `transactions_affected_count_pct = 0.0`, `relevant_clients_affected = False` (no client flows or counterparts in the MVP, documented in the report; always written explicitly, no missing key).
- `duration_hours = (end_at - aware_at) / 3600 s`; `critical_service_downtime_hours = deposits_paused_hours` (the "deposit into the treasury" service is unavailable while the vault is paused).
- `member_states_affected = len(client_member_states) if pct > 0 else 0`.
- `reputational_impact`, `data_losses`, `malicious_unauthorised_access`: profile values.
- `economic_impact_eur = round(f.at_risk_usd * usd_to_eur, 2)`.

Scenario with reaction: exposure 1,325,000, total 1,325,000, at risk 0 → pct 100.0, count 1200, States 2, economic 0.0 → `[T_9_1, T_9_4]`, major via 8(1)(b). Without reaction (raw series): at risk 375,000 → 345,000.0 EUR → `[T_9_1, T_9_4, T_9_6]`.

**4. Deadlines.** `def deadlines(aware_at, classified_at, initial_submitted_at=None) -> DoraDeadlines`:
- `initial_notification_due = min(classified_at + 4 h, aware_at + 24 h)`;
- `intermediate_report_due = (initial_submitted_at or initial_notification_due) + 72 h`;
- `final_report_due = intermediate_report_due + 30 days` (documented approximation of "one month"; phase 2: real calendar month and date of the last intermediate report).

**5. Report.** `def render_report(incident: Incident, description: str | None = None, profile: dict | None = None) -> str`. `description=None` → `template_description(incident)`. Output (exact headings, in this order):
```
# DORA initial notification (draft, human review required)
## 1. General information      (entity, type, incident reference, detection = aware_at, classification = classified_at)
## 2. Classification proposal   (Major / Not major + legal_basis)
## 3. Description               (paragraph; suffix "_(AI-drafted, review required)_" if AI)
## 4. Classification criteria (RTS 2024/1772 Art. 9)   (table | Criterion | Value | Threshold | Met |, one row per threshold)
## 5. Actions taken             (one bullet per executed action: type, readable amount, deployment, tx hash)
## 6. Deadlines (Regulation (EU) 2025/301)            (table initial / intermediate / final)
## 7. Third parties involved    (ids of the concerned dependencies: rseth, lend-eth, lend-avax, oracle)
## 8. Human review              ("This classification is a proposal. It must be reviewed and submitted by an authorised person." + submitted status)
```
Formats: ISO dates `2026-10-11T08:00:26Z`, amounts `1,325,000 USD`, tokens `150 WETH` (integer division by `10**decimals`, max 2 decimals without trailing zeros). No `None`, `nan`, `{` or `TODO` in the output.
`template_description(incident)`: `"At <aware_at> the monitoring platform raised <rule_id> (<severity>): <explanation of first alert> Automated controls paused new deposits and withdrew <saved> USD to the treasury vault. Exposure at detection: <exposure> USD; value still at risk: <at_risk> USD. Current status: <status>."`

**6. `backend/llm.py` (optional, never blocking).**
```python
def enabled() -> bool                                    # settings.BEDROCK_MODEL_ID != ""
def draft_description(facts: dict) -> tuple[str, bool]   # (text, ai_used)
def last_status() -> Literal["ok", "degraded", "unknown"]
```
- Client: `boto3.client("bedrock-runtime", region_name=settings.AWS_REGION, config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 1}))`, created lazily.
- Call: `converse(modelId=BEDROCK_MODEL_ID, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": json.dumps(facts, sort_keys=True)}]}], inferenceConfig={"maxTokens": 400, "temperature": 0})`; text = `resp["output"]["message"]["content"][0]["text"].strip()`.
- `SYSTEM`: "Write the Description paragraph of a DORA initial incident notification, in English, max 120 words, factual, using only the facts provided. Do not speculate on attribution. Do not invent numbers."
- `facts`: id, title, rule ids, severity, aware_at, USD amounts, executed actions (type, asset, deployment), status. Nothing else (no key, no private address).
- Rate: lock + `time.monotonic()`; if the last call was less than 1.0 s ago, `time.sleep(remaining)`. Module cache `{sha256(facts): text}`: same facts → no new call.
- Fallback: empty variable, exception, empty text or > 1,500 characters → `(template, False)` + log `WARNING t5.llm fallback reason=<type>`.
- The Bedrock call must **never** delay the engine: `IncidentManager` runs it in a `threading.Thread(daemon=True)`; the report first comes out with the template (`ai_drafted_sections = []`), then the thread replaces the Description section, sets `ai_drafted_sections = ["Description"]` and calls `upsert_incident` again. Constructor option `IncidentManager(store, llm_async=True)`; tests pass `llm_async=False`.

**7. `backend/incidents.py`: `IncidentManager`.** All state lives in the store (the manager can be instantiated twice, by `main.py` and by the API, without divergence). A `threading.RLock` protects `handle` and `refresh`.
```python
CONTAINMENT_SNAPSHOTS = 10
class IncidentManager:
    def __init__(self, store: Store, *, llm_async: bool = True, profile: dict | None = None): ...
    def handle(self, decisions: list[Decision], alerts: list[Alert], snapshot: Snapshot) -> Incident | None
    def refresh(self, incident_id: str) -> Incident | None   # recomputes everything from the store, upserts if changed
    def submit(self, incident_id: str, submitted_by: str) -> Incident   # KeyError / ValueError("already submitted")
def concerned_positions(alert: Alert, snapshot: Snapshot) -> set[tuple[str, str]]   # (deployment_id, asset)
```
`handle`:
1. If the store does not contain `snapshot.block_number`, use it as a fallback snapshot.
2. `current` = most recent incident with `status != "resolved"`.
3. If `current is None`: look for the first decision containing an `OPEN_INCIDENT` action (any status except `failed`). None → `return None` (isolated alerts open nothing). Otherwise create: `id = f"INC-{created_at:%Y%m%d}-{n:03d}"` (n = 1 + number of incidents in the store with this prefix), `opened_at = decision.created_at`, `detected_at = min(alert.detected_at)`, `severity` = max of the alerts, `title = f"{first_alert.title} ({', '.join(sorted(deployments concernés))})"`. Log `INFO t5.incidents opened id=… decision=… exposure_usd=…`.
4. Otherwise: attach **all** received decisions and alerts (no duplicates, arrival order).
5. `refresh(id)` then return the incident.

`concerned_positions` (rule from 2.8): R1 (asset = token, `deployment_id=None`) → all vault positions in deployments where the reserve `asset == alert.asset` has `ltv_bps > 0`; R2, R3, R4 → `(deployment_id, asset)`; R5 → all positions of the deployment. Add the `(params["deployment_id"], params["asset"])` of every `EMERGENCY_WITHDRAW` in the decisions.

`refresh` recomputes, in this order:
- **saved_usd** = Σ of `EMERGENCY_WITHDRAW` with status `executed` and an `amount`: `int(amount) / 10**decimals * price_usd`, `decimals` and `price_usd` read from the `(deployment_id, asset)` reserve of the snapshot at block `decision.block_number` (otherwise the closest one below, otherwise the latest). Scenario: 150×2,500 + 400,000 + 100×2,500 + 300,000 = **1,325,000.0**.
- **exposure_usd** = Σ `value_usd` of concerned positions, taken at the snapshot where each position becomes concerned → **1,325,000.0**.
- **at_risk_usd** = Σ `max(0, value_usd − withdrawable_usd)` of concerned positions in `store.latest_snapshot()` (missing position = 0). With reaction 0.0; raw series at block 45,201,880: **375,000.0**.
- **status**: "relevant alert" = severity ∈ {high, critical} and `exposure_usd >= 1000`. `after` = snapshots with block > last relevant alert. `contained` if `len(after) >= 10` **and** for the last snapshot no concerned position has `int(withdrawable_now) < int(supplied)`; `contained_at` = `block_time` of the first snapshot of the final continuous run where the position condition holds, no earlier than `after[9]`. Otherwise `open`, `contained_at = None` (a new relevant alert reopens). `resolved` is never set by the MVP code. Series with reaction and alert at block 45,201,812 → `contained_at = 2026-10-11T08:01:04Z` (block 45,201,832).
- **DORA** (unless `dora.submitted`, report then frozen): `aware_at = detected_at`; `end_at = contained_at or latest.block_time`; `deposits_paused_hours` = from the first executed `PAUSE_DEPOSITS` until an executed `UNPAUSE_DEPOSITS` or `latest.block_time`; `total_treasury_usd` = Σ `value_usd` of all positions + valued `idle_balances` (same definition as `StateResponse.totals.value_usd` in 2.6), at the opening snapshot. `classified_at` = `opened_at` on first evaluation; if `is_major` later goes from false to true, `classified_at = latest.block_time`.
- **timeline** fully rebuilt (stateless, sorted by `(at, block_number or 0)`):

| kind | source | text (exact example) | ref |
|---|---|---|---|
| alert | each alert | `R1_BACKING_DROP critical: rsETH backing below threshold` (`<rule_id> <severity>: <alert.title>`) | alert id |
| decision | each decision | `Decision DEC-fuji-45201812-1: critical\|exposure>=1k\|exit_possible` | decision id |
| action | `executed` action | `Deposits paused` / `Emergency withdrawal: 150 WETH from lend-eth to the vault (375,000 USD)` / `Notification sent (log, webhook, sns)` (channels read from `Action.note` in T4 format `channels: log,webhook,sns`: regex `channels: ([^;]+)`, split on `,`, `strip()`, joined with `", "`; note missing or without `channels:` → `Notification sent`); suffix ` (dry run)` if `tx_hash` starts with `0xdry` | tx hash otherwise decision id |
| action | `failed` action | `EMERGENCY_WITHDRAW failed: <note>` | decision id |
| human | `pending_approval` | `Awaiting human approval: UNPAUSE_DEPOSITS` | decision id |
| human | action whose `note` contains a human decision (final status `approved`, `rejected`, `executed`, `failed` or `skipped` after approval) | `UNPAUSE_DEPOSITS approved by treasury-signer-1`: `re.search(r"(approved\|rejected) by ([^;]+)", note)` → `f"{type} {m[1]} by {m[2].strip()}"`; no match → no human event | decision id |
| chain | 1st snapshot where `available_liquidity == "0"` on a reserve of a concerned position | `WETH liquidity on lend-eth reaches zero` | None |
| dora | classification | `DORA classification proposed: major (9(1), 9(4))` | incident id |
| human | submission | `DORA initial notification submitted by <submitted_by>` | incident id |
| decision | `contained_at` | `Incident contained: no exposed position left` | incident id |

Logs: `INFO t5.incidents status id=… from=open to=contained at=…`, `INFO t5.dora classified id=… major=true thresholds=9(1),9(4)`.

**8. Dependencies (`backend/config/dependencies.yaml` + `incidents.dependency_statuses(store, now=None) -> list[Dependency]`).** Each entry = `Dependency` fields + `check` (internal key, removed before validation):

| id | kind | criticality | fallback | check → status |
|---|---|---|---|---|
| `rpc-fuji` | rpc | critical | `RPC_FALLBACK_URL` | `freshness`: age of the latest snapshot (`now − block_time`) ≤ 30 s ok, ≤ 120 s degraded, otherwise down; no snapshot unknown |
| `aws-compute` | cloud | critical | `make demo` locally | `none` → unknown |
| `aws-sns` | alerting | important | webhook | `none` → unknown |
| `aws-s3` | cloud | important | `data/evidence` + on-chain hash | `none` → unknown |
| `bedrock` | ai_model | standard | deterministic template | `llm.last_status()`; unknown if never called |
| `oracle` | oracle | critical | second oracle (planned) | ok if all `price_usd > 0`, otherwise degraded |
| `lend-eth`, `lend-avax` | protocol | critical | — | reserve `paused` → down; reserve `frozen` or vault position `withdrawable_ratio_bps < 10000` → degraded; otherwise ok |
| `rseth` | bridge | important | — | `backing_ratio_bps` ≥ 9900 ok, ≥ 5000 degraded, otherwise down |

**9. API (`backend/api/incidents.py`, `router = APIRouter(tags=["incidents"])`).** Read `settings.USE_FIXTURES` **on every request**. Fixtures mode: T0 skeleton behaviour (validated fixture, `submit` modifies a copy). Live mode: `IncidentManager(store)` then `refresh` before every read. `SubmitBody(submitted_by: str = Field(min_length=1))` → 422 if empty. 404 `{"detail": "incident not found"}`; 409 `{"detail": "incident has no DORA assessment"}` or `{"detail": "already submitted"}` ("incident already submitted" case of 2.9); 422 for empty `submitted_by` ("invalid body" case of 2.9, handled by FastAPI validation). Report: `PlainTextResponse(md, media_type="text/markdown; charset=utf-8")`.

**10. `mk/t5.mk`.**
```make
test-t5:      ## T5 tests
	python -m pytest backend/tests/test_t5_*.py -q
dora-report:  ## write data/reports/$(ID).md from the running backend
	python -m backend.dora report --id $(ID) --api http://127.0.0.1:8000
dora-demo:    ## print the report for the scenario facts (offline, no API)
	python -m backend.dora demo
```
`report` does a GET on `/api/incidents/<ID>/report.md` (urllib, 5 s timeout), writes `data/reports/<ID>.md`, prints it; exit code 1 with a clear message if the API does not respond.

#### Tests that must pass

Global command: `make test-t5` (= `python -m pytest backend/tests/test_t5_*.py -q`, never `-k`). Shared factories in `backend/tests/test_t5_factories.py` (no `test_*` functions): `load_attack()` (41 snapshots), `make_reacted_series()` (copy of the series; from block 45,201,814: positions `supplied = withdrawable_now = "0"`, `withdrawable_ratio_bps = 10000`, `value_usd = withdrawable_usd = 0.0`, `deposits_paused = True`, `idle_balances = {"WETH": "250000000000000000000", "USDC": "700000000000"}`), `make_alert_r1()` (`ALT-fuji-45201812-R1_BACKING_DROP-global-rsETH`, critical, `deployment_id=None`, asset rsETH, block 45,201,812, `block_time` 08:00:24Z, `detected_at` 08:00:26Z, exposure 1,325,000.0, title **exactly** T3's `rsETH backing below threshold`, explanation in T3 format `rsETH backing fell to 19.4 % (1,200 WETH backing for 6,200 rsETH supply).`, `metrics` in T3 format `{"backing_ratio_bps": 1935, "backing": 1200.0, "total_supply": 6200.0, "threshold_bps": 9900, "exposed_deployments": "lend-eth,lend-avax"}`), `make_decision_r1(no_reaction=False)` (`DEC-fuji-45201812-1`, `created_at` 08:00:26Z, 8 actions from 2.8: NOTIFY, PAUSE_DEPOSITS, 4 × EMERGENCY_WITHDRAW lend-eth WETH `150e18`, lend-eth USDC `400000e6`, lend-avax WETH `100e18`, lend-avax USDC `300000e6` with `tx_hash = "0x" + f"{i:02x}" * 32`, NOTIFY `note="channels: log,webhook,sns"`, OPEN_INCIDENT, UNPAUSE_DEPOSITS human `pending_approval`; `no_reaction=True` → the 4 withdrawals `skipped`, `amount=None`, to simulate a platform that could not react), `FakeStore`, `run_series(manager, snapshots, at={block: (decisions, alerts)})` (adds each snapshot then calls `handle`, with `[]`, `[]` outside the given blocks).

| Id | Type | File::test | Setup | Expected result |
|---|---|---|---|---|
| T5-01 | unit | `test_t5_dora.py::test_no_critical_service_never_major` | all thresholds met, `critical_services_affected=False` | `is_major is False`, 7 labels in `thresholds_met`, `legal_basis` contains `not major, no critical service` |
| T5-02 | unit | `::test_single_threshold_not_major` | critical, `clients_affected_pct=15`, rest at 0 | `thresholds_met == [T_9_1]`, `is_major is False` |
| T5-03 | unit | `::test_malicious_access_alone_major` | critical, `malicious_unauthorised_access=True` alone | `== [T_9_5B]`, major, `Art. 8(1)(a)` in `legal_basis` |
| T5-04 | unit | `::test_two_thresholds_major` (parametrised over 6 pairs) | e.g. 9(2)+9(4), 9(3)+9(6) | `is_major is True`, `Art. 8(1)(b)` |
| T5-05 | unit | `::test_boundaries` (parametrised) | pct 10 / 10.01; count 100000 / 100001; duration 24 / 24.01; downtime 2 / 2.01; States 1 / 2; 100000 / 100000.01 EUR; and one case per optional 9(1) field: `counterparts_affected_pct` 30 / 30.01, `transactions_affected_count_pct` 10 / 10.01, `relevant_clients_affected` False / True | first not met, second met (for the three optional ones: `T_9_1` in `thresholds_met` only for the second) |
| T5-06 | unit | `::test_criterion_counts_once` | critical, pct 50 and count 200,000 | `[T_9_1]`, not major; `data_losses` + malicious → 9(5) counts 1 |
| T5-07 | unit | `::test_deadlines_nominal` | aware `2026-10-11T08:00:26Z`, classified `08:02:26Z` | `12:02:26Z`, `2026-10-14T12:02:26Z`, `2026-11-13T12:02:26Z` |
| T5-08 | unit | `::test_deadlines_24h_cap` | aware `2026-10-11T00:00:00Z`, classified `22:00:00Z` | initial `2026-10-12T00:00:00Z` |
| T5-09 | unit | `::test_deadlines_after_submission` | T5-07 + submitted `2026-10-11T10:00:00Z` | intermediate `2026-10-14T10:00:00Z`, final `2026-11-13T10:00:00Z` |
| T5-10 | unit | `::test_scenario_facts` | facts with reaction + profile | pct 100.0, count 1200, States 2, economic 0.0, `[T_9_1, T_9_4]`, major |
| T5-11 | unit | `::test_counterfactual_facts` | `at_risk_usd=375000` | economic 345000.0, `[T_9_1, T_9_4, T_9_6]` |
| T5-12 | unit | `::test_report_markdown` | T5-17 incident (`llm_async=False`, LLM disabled) | 1st line = exact H1 title, the 8 `##` headings present in order, contains `1,325,000 USD` and `INC-20261011-001`, no match for the regex `\bNone\b\|\bnan\b\|TODO\|\{[a-z_]+\}` (careful: "financial" contains `nan`, hence the `\b`) |
| T5-13 | unit | `test_t5_llm.py::test_disabled_uses_template` | `BEDROCK_MODEL_ID=""`, `boto3.client` patched to raise | `(template, False)`, incident `ai_drafted_sections == []` |
| T5-14 | unit | `::test_bedrock_error_falls_back` | stub whose `converse` raises `ReadTimeoutError` | template, `last_status() == "degraded"` |
| T5-15 | unit | `::test_bedrock_success` | stub returning a paragraph; `llm_async=False` | `converse` called with `modelId`, `temperature=0`, `maxTokens=400`; `ai_drafted_sections == ["Description"]`; text in section 3 |
| T5-16 | unit | `::test_rate_limit_and_cache` | fake clock | 2 different facts back to back → `sleep(≈1.0)`; same facts → only 1 call |
| T5-17 | integration | `test_t5_incidents.py::test_opens_one_incident_reacted` | `make_reacted_series()`, R1 decision at block 45,201,812 | 1 incident `INC-20261011-001`, `contained`, `contained_at = 2026-10-11T08:01:04Z`, `saved_usd 1325000.0`, `at_risk_usd 0.0`, `exposure_usd 1325000.0`, `severity critical`, DORA major `[T_9_1, T_9_4]`, `initial_notification_due 2026-10-11T12:00:26Z` |
| T5-18 | integration | `::test_no_open_incident_action` | warning decision (NOTIFY only) | `handle` → `None`, `store.incidents() == []` |
| T5-19 | integration | `::test_attaches_later_decisions_raw` | raw series, R1 `no_reaction=True` + high R2 decision at block 45,201,826 (with OPEN_INCIDENT) | a single incident, 2 decisions, 2 alerts, `open`, `saved_usd 0.0`, `at_risk_usd 375000.0`, thresholds `[T_9_1, T_9_4, T_9_6]` |
| T5-20 | integration | `::test_timeline` | T5-17 | kinds ⊇ {alert, decision, action, human, dora}; sorted by `at`; 4 `Emergency withdrawal` events with `ref` = tx hash; contains `Emergency withdrawal: 150 WETH from lend-eth to the vault (375,000 USD)`, `Notification sent (log, webhook, sns)` and `R1_BACKING_DROP critical: rsETH backing below threshold` |
| T5-21 | integration | `::test_human_approval_picked_up` | T5-17, action 7 → `executed`, `note="approved by treasury-signer-1; "` (T4 format), `refresh`; then `rejected` variant, `note="rejected by risk-officer"` | event `UNPAUSE_DEPOSITS approved by treasury-signer-1` (no trailing `;` or space); variant: `UNPAUSE_DEPOSITS rejected by risk-officer`; no more `Awaiting human approval` event |
| T5-22 | integration | `::test_reopen_on_new_relevant_alert` | T5-17 then critical alert with exposure 5,000 | `open`, `contained_at is None` |
| T5-23 | integration | `::test_idempotent_and_resolved` | `handle` 2× same decision; then incident forced to `resolved` + new OPEN_INCIDENT decision | no duplicate; new id `INC-20261011-002` |
| T5-24 | API | `test_t5_api.py::test_fixture_mode` | `USE_FIXTURES=true`, `FastAPI()` + T5 router | list of 1, detail 200, `UNKNOWN` → 404 |
| T5-25 | API | `::test_live_mode` | `USE_FIXTURES=false`, T5-17 store (monkeypatch `backend.store.store`) | detail `saved_usd 1325000.0`; `report.md` → `content-type` starts with `text/markdown`, body starts with the H1 title |
| T5-26 | API | `::test_submit` | same | 1st POST 200 `submitted true`; 2nd → 409 `{"detail": "already submitted"}` (incident already submitted, 2.9); `submitted_by=""` → 422 (invalid body, 2.9); unknown id → 404 |
| T5-27 | unit | `test_t5_dependencies.py::test_statuses` | latest snapshot = line 41 of the raw series, `now = block_time + 10 s` | 9 validated `Dependency` entries; `rseth down`, `lend-eth degraded`, `lend-avax ok`, `rpc-fuji ok`, `aws-sns unknown`, `bedrock unknown`; `now + 200 s` → `rpc-fuji down` |

#### Definition of done

- [ ] `make test-t5` green (T5-01 to T5-27), without network or AWS.
- [ ] `classify` depends only on `DoraCriteria`; each Art. 9 threshold has a boundary test.
- [ ] With `USE_FIXTURES=false` and the engine running on anvil, an attack (`make attack SEED=42`) produces exactly one `contained` incident, `saved_usd ≈ 1,325,000`, downloadable report.
- [ ] `make dora-demo` prints a complete report; `make dora-report ID=INC-…` writes `data/reports/INC-….md`.
- [ ] Bedrock off or failing: no engine blocking, report from the template.
- [ ] No file changes outside "Owned files"; requests written in `docs/contract-requests.md`.

#### Known pitfalls

- **Never** modify a `Decision` (its `record_hash` is anchored by T4): the decision → incident link goes through `Incident.decision_ids`, not through the `params` of `OPEN_INCIDENT`.
- `handle` is called by the engine via `await asyncio.to_thread(...)`, one call at a time in snapshot order (2.10): it does not block the API, but a slow `handle` delays processing of the following snapshots. So no synchronous network call (Bedrock in a thread), no exception bubbling up (try/except + `ERROR` log, return `None`). The API calls `refresh` from another thread: hence the `RLock`.
- `store.reset()` (via `make reset` / `POST /api/demo/reset`) clears incidents and increments `store.generation`: the Bedrock thread records `generation` at start and does not call `upsert_incident` if it has changed (otherwise a deleted incident reappears). During maintenance mode (2.10), the engine evaluates no rules: no decision arrives, nothing special to do on the T5 side.
- An `executed` `EMERGENCY_WITHDRAW` with `amount="0"` (nothing to withdraw, 2.2) counts 0 in `saved_usd`; a `failed` withdrawal (`MiniLend: paused`) produces the event `EMERGENCY_WITHDRAW failed: <note>`.
- Human approvals do not call `handle`: hence `refresh` on every API read.
- Amounts in base units: `int(amount)`, never `float(amount)` before the final division.
- `store.snapshots()` may have lost the opening snapshot (limited window): fall back to the closest one, then the latest.
- The `incident.json` fixture serves as a shape model; our numeric expectations come from the factories (T0 then regenerates it with our real numbers).
- T0's regenerated "with reaction" fixtures: R1 alert and `DEC-fuji-45201812-1` at block 45,201,812, like our factories (the decision id reuses the block of the alerts' snapshot). Do not hard-code any block number in production code.
- `datetime` always with UTC timezone; serialise with `Z`.
- Legal text: have the T9 person review the Art. 8(1)(a)/(b) wording against EUR-Lex before the demo.

#### Later (phase 2)

- `POST /api/incidents/{id}/resolve` route (human) and `resolved` status; intermediate and final reports (templates, deadlines in calendar months).
- 9(1) counterparts and transaction count criteria fed by real data; detection of recurring incidents (RTS Art. 16).
- Anchoring the incident hash in `EvidenceRegistry` (`kind = "incident"`), S3 export of the report.
- Real SNS, S3, EC2 statuses (probes); dependency status history.
- `FULL_EXIT` counted in `saved_usd`; correlation of several simultaneous incidents.

#### Claude Code starter prompt

```
You are working on task T5 (incident and DORA) from the TASKS.md file at the repo root.
1. Read sections 1 and 2 of TASKS.md, then the whole T5 section, then backend/models.py,
   backend/settings.py and fixtures/snapshots_attack.jsonl (a few lines).
2. Modify ONLY: backend/incidents.py, backend/dora.py, backend/llm.py,
   backend/config/dora_profile.yaml, backend/config/dependencies.yaml,
   backend/api/incidents.py, mk/t5.mk, backend/tests/test_t5_*.py.
   Any other change (models.py, main.py, response.py, fixtures, contract): do not edit,
   write the request in docs/contract-requests.md and tell me.
3. Start with backend/tests/test_t5_factories.py then tests T5-01 to T5-27 (they must
   fail), then dora.py, llm.py, incidents.py, api/incidents.py, in that order.
4. No dependency on other tasks: decisions and alerts built by hand per 2.8,
   FakeStore if backend/store.py is missing, empty BEDROCK_MODEL_ID, no network call in tests.
5. Never modify a Decision. Amounts in base units (int), UTC ISO dates with Z.
6. Before each commit: make test-t5 green. Small commits, prefix "t5:", push often after each green test.
```

**Contract.** The three optional Art. 9(1) fields (`counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`) are now in `DoraCriteria` (2.6); no pending contract request for T5.


---
### T6 · Dashboard

**Goal.** Build the web dashboard (`frontend/` folder) that shows the jury, at a glance and in plain English: the state of the treasury and markets, the R1..R5 alerts and the decisions taken (with their transactions), the incident and the pre-filled DORA report, the verifiable evidence for each decision, the third-party register, the evaluation metrics and a demo panel (launch the attack, reset). The front end computes **no** detection rule: it displays what the API returns (section 2.9), polling the backend every 2 s.

**Depends on.**
- T0 → `frontend/src/types.ts` (mirror of `models.py`, owned by T0), `fixtures/*.json` (API responses), backend skeleton that already serves every route with `USE_FIXTURES=true`, root `Makefile` that includes `mk/*.mk` → **mock**: `VITE_USE_FIXTURES=true` mode (the front end imports `fixtures/*.json` directly, no backend needed), then `make backend` (T0 skeleton).
- T3 → `GET /api/health`, `/api/state`, `/api/series`, `/api/alerts` → mock: `health.json`, `state.json`, `series.json`, `alerts.json`.
- T4 → `GET /api/decisions`, `POST /api/decisions/{id}/approve`, `POST /api/verify/{decision_id}` → mock: `decisions.json`, `verify.json`, and in-memory simulated approval (step 3).
- T5 → `GET /api/incidents`, `/api/incidents/{id}`, `/api/incidents/{id}/report.md`, `POST /api/incidents/{id}/submit`, `GET /api/dependencies` → mock: `incident.json`, `dependencies.json`, in-memory simulated submission.
- T2 → `POST /api/demo/attack`, `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` → mock: `demo_run.json`.
- T7 → `GET /api/metrics` → mock: `metrics.json`.

**Unblocks.** T9 (screenshots, video, demo script), T8 (serves the static build `frontend/dist/` on EC2), the jury (this is what they see).

**Owned files.**
- All of `frontend/` **except** `frontend/src/types.ts`: `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`, `.env.example`, `src/main.tsx`, `src/App.tsx`, `src/index.css`, `src/api.ts`, `src/fixtureDb.ts`, `src/hooks/usePolling.ts`, `src/hooks/useNow.ts`, `src/lib/format.ts`, `src/lib/labels.ts`, `src/lib/chart.ts`, `src/components/*.tsx`, `src/pages/*.tsx`, `src/test/setup.ts`, `src/**/*.test.ts(x)`.
- `mk/t6.mk`.
- **Not T6's**: `frontend/src/types.ts` belongs to **T0** (mirror of `models.py`, updated through the 2.12 process). T6 imports it and never modifies it. If it is missing or diverges from `models.py`, T6 writes a request in `docs/contract-requests.md` and, meanwhile, uses a local copy (`src/test/types.local.ts`) **only in tests**; application code always imports `src/types.ts`.

**Read before starting.** TASKS.md sections 1 (especially 1.2 scenario and 1.5 ownership), 2.5 (conventions), 2.6 (models and definitions of `totals`, `risk_level`, `EvalMetrics.synthetic`), 2.7 (rules R1..R5 and thresholds), 2.8 (matrix, `pending_approval` actions), 2.9 (routes and error codes), 2.12; `backend/models.py`; `frontend/src/types.ts` (T0); `fixtures/state.json`, `fixtures/series.json`, `fixtures/verify.json`, `fixtures/demo_run.json`.
Warning: `alerts.json`, `decisions.json`, `incident.json`, `state.json`, `series.json` are **stale** (old ids `D1..D7`, only WETH withdrawn) and will be regenerated to follow 2.7/2.8 (R1 alert and decision `DEC-fuji-45201812-1` at block 45,201,812, everything pulled back to the vault). The code must depend neither on the old ids nor on the exact number of positions: tests use either scenario invariants, values read from the fixture, or objects written in the test.

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| `GET /api/health` | `Health` | T3 | `fixtures/health.json` |
| `GET /api/state` | `StateResponse` (totals: `value_usd`, `withdrawable_usd`, `idle_usd`, `at_risk_usd`, defined in 2.6); **503** `{"detail":"no snapshot yet"}` as long as the engine has not read any block | T3 | `fixtures/state.json` |
| `GET /api/series?deployment_id=&asset=&limit=300` | chronological `SeriesPoint[]` | T3 | `fixtures/series.json` (object keyed by `"<deployment_id>:<asset>"` → `SeriesPoint[]`; also accept a raw array) |
| `GET /api/alerts?since_block=0` | `Alert[]` newest first | T3 | `fixtures/alerts.json` |
| `GET /api/decisions` | `Decision[]` newest first | T4 | `fixtures/decisions.json` |
| `POST /api/decisions/{id}/approve` | body `{"action_index": int, "approver": str, "approve": bool}` → `Decision` | T4 | in-memory `fixtureDb.approve()` |
| `POST /api/verify/{decision_id}` | `VerifyResult` | T4 | `fixtures/verify.json` |
| `GET /api/incidents`, `/api/incidents/{id}` | `Incident[]`, `Incident` | T5 | `fixtures/incident.json` (single object, wrap in a list) |
| `GET /api/incidents/{id}/report.md` | markdown text | T5 | `incident.dora.report_markdown` |
| `POST /api/incidents/{id}/submit` | body `{"submitted_by": str}` → `Incident` | T5 | in-memory `fixtureDb.submit()` |
| `GET /api/dependencies` | `Dependency[]` | T5 | `fixtures/dependencies.json` |
| `POST /api/demo/attack` (body `{"seed": int, "variant": "default" \| "slow" \| "usdc"}`), `POST /api/demo/reset`, `GET /api/demo/runs/{run_id}` | `DemoRun`; 409 if a run is already in progress | T2 | `fixtures/demo_run.json` (seed and variant replaced by those sent) |
| `GET /api/metrics` | `EvalMetrics` (`*_rate` from 0 to 1, `*_pct_*` from 0 to 100, `ttd_blocks_*` = -1 if nothing detected) | T7 | `fixtures/metrics.json` |
| `EXPLORER_URL` (root `.env`) | URL, default `https://testnet.snowtrace.io` | T0 (2.1) | default value |
| `VITE_API_URL`, `VITE_USE_FIXTURES` (`frontend/.env`) | URL; absent → `http://localhost:8000` in dev, `''` in production build (relative `/api/...` calls on the same origin, T8's nginx serves the front end and the API); `"true"`/`"false"` (default `false`) | T6 | `frontend/.env.example` shipped with `VITE_USE_FIXTURES=true` |
| `frontend/src/types.ts` | TS types mirroring `models.py` | T0 | local copy in tests only (see "Owned files") |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| Dev application | `make frontend` → `http://localhost:5173` | everyone, T9 (demo) |
| Static build | `make frontend-build` → `frontend/dist/` (HTML + JS + CSS, no secrets) | T8 (serves `dist/` on EC2 with nginx, same origin as `/api`: `VITE_API_URL` left empty at build) |
| Front-end routes | `/` Overview, `/charts`, `/alerts`, `/incident`, `/evidence`, `/dependencies`, `/metrics`, `/demo` | T9 (video, screenshots, links in the README) |
| HTTP calls | exactly those of 2.9; writes only: approve, verify, submit, demo attack/reset | T4, T5, T2 |
| `make test-t6` | exit code 0 if typecheck, build and vitest pass (in that order) | T0 (`make test`), T8 (CI) |

#### Detailed specification

**1. Skeleton and tooling.**
- `npm create vite@latest frontend -- --template react-ts`, then: `react-router-dom@6`, `recharts@2`, `react-markdown@9`, `remark-gfm@4`, `tailwindcss@3 postcss autoprefixer`, in dev `vitest@1 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event`.
- `package.json` scripts: `"dev": "vite --port 5173"`, `"build": "vite build"`, `"typecheck": "tsc --noEmit"`, `"test": "vitest run"`, `"preview": "vite preview --port 5173"`.
- `vite.config.ts`:
  - alias `@fixtures` → `path.resolve(__dirname, '../fixtures')`; `server.fs.allow: ['..']` (otherwise Vite refuses to serve files outside `frontend/`);
  - `const rootEnv = loadEnv(mode, path.resolve(__dirname, '..'), '')` then `define: { __EXPLORER_URL__: JSON.stringify(rootEnv.EXPLORER_URL || 'https://testnet.snowtrace.io') }`. Inject **only** this variable: the root `.env` contains private keys;
  - `test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', globals: true }`;
  - option (dev only): `server.proxy: { '/api': 'http://localhost:8000' }`, which lets you run the front end with `VITE_API_URL=` (empty) and relative calls, as in production. By default we do not depend on it: in dev, `API_URL` is `http://localhost:8000` (CORS `*`).
- `tsconfig.json`: `strict: true`, `resolveJsonModule: true`, `paths: { "@fixtures/*": ["../fixtures/*"] }`, `src/vite-env.d.ts` declares `declare const __EXPLORER_URL__: string` and `ImportMetaEnv { VITE_API_URL?: string; VITE_USE_FIXTURES?: string }`.
- `src/test/setup.ts`: `import '@testing-library/jest-dom/vitest'`, `ResizeObserver` polyfill (empty class), `afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); })`.
- `frontend/.env.example`: `VITE_API_URL=http://localhost:8000` (comment: "leave empty in production: same origin, nginx serves `/api`") and `VITE_USE_FIXTURES=true`.
- `mk/t6.mk` (`target: ; command` syntax, no tabs to deal with; never redefines `NETWORK`, which comes from the root `Makefile`):
  ```make
  .PHONY: frontend frontend-build test-t6
  frontend:        ; cd frontend && npm run dev
  frontend-build:  ; cd frontend && npm ci && npm run build
  test-t6:         ; cd frontend && npm run typecheck && npm run build && npm run test
  ```

**2. `src/types.ts` (T0's file, read by T6).** T6 neither creates nor modifies this file: it imports it everywhere (`import type { StateResponse } from '../types'`). What you can expect from it, to read it and to write the local test copy if T0 has not delivered it yet. Translation rules used by T0: `str` → `string`; `int`/`float` → `number`; `datetime` → `string` (ISO 8601); `Optional[X] = None` → `x: X | null` (pydantic serialises `None` as `null`, the key is always present, never `exclude_none`, 2.5); field with a default → **required** field on the TS side (always present in the JSON); `Literal[...]` → string union; `dict[str, X]` → `Record<string, X>`. Examples:
```ts
export type Severity = 'info' | 'warning' | 'high' | 'critical';
export type Network = 'local' | 'fuji' | 'replay';
export type ActionType = 'NOTIFY' | 'PAUSE_DEPOSITS' | 'EMERGENCY_WITHDRAW' | 'FULL_EXIT' | 'UNPAUSE_DEPOSITS' | 'OPEN_INCIDENT';
export type ActionStatus = 'planned' | 'executed' | 'failed' | 'skipped' | 'pending_approval' | 'approved' | 'rejected';
export interface Action { type: ActionType; mode: 'auto' | 'human'; status: ActionStatus;
  params: Record<string, string | number | boolean | string[]>; tx_hash: string | null; amount: string | null;
  executed_at: string | null; note: string | null; }
export interface StateResponse { network: Network; chain_id: number; block_number: number; block_time: string;
  updated_at: string; risk_level: Severity; open_incident_id: string | null; vault: VaultStatus;
  positions: PositionSnapshot[]; reserves: ReserveSnapshot[]; tokens: TokenSnapshot[]; totals: Record<string, number>; }
```
All models of 2.6 are in it, plus `Health`, `SeriesPoint`, `DemoRun`, `EvalMetrics`, `Dependency`, `DoraAssessment`, `DoraCriteria` (with the three Art. 9(1) fields added in 2.6: `counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`), `DoraDeadlines`, `TimelineEvent`, `VerifyResult`. `rule_id` stays `string` (the Python says `str`); the R1..R5 labels live in `lib/labels.ts`. If `src/types.ts` is missing or diverges from the fixtures (T6-15 red): request in `docs/contract-requests.md`, never a direct edit.

**3. API client `src/api.ts` and mock `src/fixtureDb.ts`.**
```ts
export const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
// production: '' → relative fetch('/api/...'), same origin (T8's nginx serves dist/ and /api)
export function isFixtureMode(): boolean { return import.meta.env.VITE_USE_FIXTURES === 'true'; } // read on every call (testable with vi.stubEnv)
export class ApiError extends Error { constructor(public status: number, public detail: string) { super(`${status}: ${detail}`); } }
export const api = {
  health(): Promise<Health>; state(): Promise<StateResponse>;
  series(deploymentId: string, asset: string, limit = 300): Promise<SeriesPoint[]>;
  alerts(sinceBlock = 0): Promise<Alert[]>; decisions(): Promise<Decision[]>;
  approve(decisionId: string, body: { action_index: number; approver: string; approve: boolean }): Promise<Decision>;
  verify(decisionId: string): Promise<VerifyResult>;
  incidents(): Promise<Incident[]>; incident(id: string): Promise<Incident>; incidentReport(id: string): Promise<string>;
  submitIncident(id: string, submittedBy: string): Promise<Incident>;
  dependencies(): Promise<Dependency[]>; metrics(): Promise<EvalMetrics>;
  demoAttack(seed: number, variant: DemoVariant = 'default'): Promise<DemoRun>; demoReset(): Promise<DemoRun>; demoRun(runId: string): Promise<DemoRun>;
};
export type DemoVariant = 'default' | 'slow' | 'usdc';
export function isNoSnapshotYet(e: unknown): boolean { return e instanceof ApiError && e.status === 503; }
```
- Real mode: `fetch(\`${API_URL}/api/...\`)`, parameters via `URLSearchParams` (order: `deployment_id`, `asset`, `limit`), POST with `headers: {'Content-Type': 'application/json'}` and `body: JSON.stringify(...)` (`verify` and `demoReset`: POST with no body). Non-2xx status → `throw new ApiError(status, json.detail ?? statusText)`. `incidentReport` reads `res.text()`.
- Error codes from 2.9 and display: **503** `no snapshot yet` → "Waiting for first block" state (see 7 and 8, this is not an outage); **409** → message as is ("action is not pending approval", "a demo run is already running", "incident already submitted") and `refresh()`; **400** / **404** / **422** → red message with `detail`. Vitest tests run with `import.meta.env.DEV === true`, so `API_URL` there is `http://localhost:8000`.
- Fixture mode: each function delegates to `fixtureDb`, which loads the JSON via `import('@fixtures/state.json')` (dynamic import: fixtures are not bundled in the real build), makes a deep copy (`structuredClone`) on first access, and keeps it in memory. Cast `as unknown as T` (imported JSON has wide `string` types). Simulated behaviours:
  - `series(dep, asset)`: `data[\`${dep}:${asset}\`] ?? []` if the object is keyed, the array as is otherwise, then `slice(-limit)`;
  - `approve(id, body)`: action `body.action_index` → `status = body.approve ? 'executed' : 'rejected'`, `note = (body.approve ? 'approved by ' : 'rejected by ') + body.approver`; returns the decision; unknown id → `ApiError(404, 'decision not found')`;
  - `verify(id)`: `{...verify.json, decision_id: id}`;
  - `incidents()`: `[incident.json]`; `submitIncident`: `dora.submitted = true`, `submitted_by`, `submitted_at = new Date().toISOString()`;
  - `demoAttack(seed, variant)`: `{...demo_run.json, seed, variant, run_id: \`RUN-<yyyymmddHHMMSS>-attack-${seed}\`, status: 'running'}`; `demoReset`: same with `kind: 'reset'`, `status: 'done'`.
  - No `fetch` is called in fixture mode (test T6-14).

**4. Polling hook `src/hooks/usePolling.ts`.**
```ts
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 2000, deps: unknown[] = []):
  { data: T | undefined; error: Error | undefined; loading: boolean; lastUpdated: number | undefined; refresh: () => Promise<void> }
```
Algorithm: immediate call on mount, then a **`setTimeout` chain** (the next call is scheduled when the previous one has finished, never two requests in flight); on error, keep the last `data` and fill `error`; a success clears `error`; `refresh()` triggers a call right away (used after approve/submit/verify); on unmount and on `deps` change: `clearTimeout` + `cancelled` flag (React 18 StrictMode mounts twice in dev). Intervals: 2,000 ms for health, state, alerts, decisions, series, incidents, demo run; 30,000 ms for dependencies and metrics.
`src/hooks/useNow.ts`: `useNow(tickMs = 1000): number` (refreshed Date.now()), for countdowns.
A `DashboardDataProvider` (React context in `App.tsx`) polls `health`, `state`, `alerts`, `decisions` once and shares them (header, Overview, Charts, Alerts, Evidence); the other pages poll their own routes.

**5. Formatting `src/lib/format.ts` (pure functions, tested in T6-03).**
- `formatUsd(n: number): string` → `Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits: 0})`: `1325000` → `"$1,325,000"`.
- `formatUnits(base: string, decimals: number, maxFrac = 2): string` with **BigInt** (never `Number` on an amount in base units): `("1850000000000000000000", 18)` → `"1,850"`; `("400000000000", 6)` → `"400,000"`; `("1500000000000000000", 18)` → `"1.5"`; `("0", 18)` → `"0"`.
- `unitsToNumber(base: string, decimals: number): number` for charts only (2-decimal precision).
- `formatBpsPct(bps: number): string` → `(Math.round(bps / 10) / 10).toFixed(1) + '%'`: `1935` → `"19.4%"`, `10000` → `"100.0%"`, `6714` → `"67.1%"`.
- `withdrawableTone(bps): 'ok' | 'warn' | 'bad'`: `≥ 8000` ok, `5000..7999` warn, `< 5000` bad (R4 thresholds). `utilizationTone(bps)`: `< 9000` ok, `9000..9799` warn, `≥ 9800` bad (R3 thresholds). `backingTone(bps)`: `≥ 9900` ok, otherwise bad (R1).
- `shortHash(h)` → `"0x433c…74cc"` (first 6 + `…` + last 4 characters).
- `formatCountdown(dueIso: string, nowMs: number): string`: `"4 h 00 min left"`, `"2 d 3 h left"` beyond 48 h, `"overdue by 1 h 05 min"` if past.
- `formatUtc(iso)` → `"2026-10-11 08:00:27 UTC"` (always display UTC, explicitly).
- `tones` → Tailwind classes: ok `bg-green-600`, warn `bg-amber-500`, bad `bg-red-600`; severities: info `bg-slate-500`, warning `bg-amber-500`, high `bg-orange-600`, critical `bg-red-600` (white text, word written in capitals: colour is never the only information).

**6. Labels `src/lib/labels.ts`.** `RULE_LABELS`: `R1_BACKING_DROP` "Bridged token backing drop", `R2_LIQUIDITY_DROP` "Market liquidity drop", `R3_UTILIZATION_HIGH` "Market utilization high", `R4_POSITION_STUCK` "Our position is stuck", `R5_RESERVE_FROZEN` "Reserve frozen or paused"; fall back to the raw id. `ACTION_LABELS`: NOTIFY "Notify the team", PAUSE_DEPOSITS "Pause new deposits", EMERGENCY_WITHDRAW "Emergency withdrawal to the vault", FULL_EXIT "Full exit", UNPAUSE_DEPOSITS "Resume deposits", OPEN_INCIDENT "Open incident". `DEPLOYMENT_LABELS`: `lend-eth` "Lending protocol (Ethereum deployment)", `lend-avax` "Lending protocol (Avalanche deployment)".

**7. Layout (`App.tsx`, `components/Layout.tsx`).** Sidebar with the 8 routes; badge with the number of `pending_approval` actions on "Alerts & decisions". Header: network (`FUJI`/`LOCAL`), current block, green/red dot for `rpc_ok`, `engine_running`, "Updated 2 s ago" (from `lastUpdated`), "Operator name" field (stored in `localStorage['sh.operator']`, default `dashboard-operator`, read/write inside a `try/catch`), used as `approver` and `submitted_by`. Yellow banner `FIXTURE MODE: data from fixtures/, no backend` if `isFixtureMode()`. Grey banner `Waiting for first block: the monitoring engine has not read the chain yet` if `state` polling returns 503 (`isNoSnapshotYet`): this is not an outage, polling continues and the banner disappears at the first snapshot. Red banner `Backend unreachable: showing last data from block N` if `state` polling fails for any other reason (network, 5xx other than 503). Amber banner `Data is stale` if `now - updated_at > 15 s` (disabled in fixture mode).
Jury readability: key figures in `text-4xl font-bold tabular-nums`, 16 px base text, AA contrast, bars with `role="progressbar"` and `aria-valuenow`, visible keyboard focus, no abbreviations (no "bps" on screen: everything in %).

**8. Overview page (`/`, `pages/Overview.tsx`).**
- As long as `state` has never been received and the error is a 503: a single box `data-testid="waiting-first-block"` with "Waiting for first block" and a waiting indicator, instead of the cards (no misleading `$0`). Same rule for Charts, Alerts and Evidence, which depend on `state`.
- 4 cards (data-testid `total-value`, `total-withdrawable`, `total-idle`, `total-at-risk`): "Total treasury value", "Withdrawable now", "Back in the vault (idle)", "At risk" ← `state.totals.value_usd`, `withdrawable_usd`, `idle_usd`, `at_risk_usd`, with `formatUsd`. "At risk" in red if > 0. The front end recomputes nothing: the definitions are those of 2.6 (`value_usd` = positions + idle; `at_risk_usd` = Σ (value − withdrawable) of positions); short tooltip under each card restating that definition in English.
- Risk badge (`data-testid="risk-badge"`): `state.risk_level` in capitals (`CRITICAL`) with the severity colour; subtitle "Highest severity of conditions still true at block N" (2.6: an alert whose condition has gone no longer counts, so `INFO` is normal after things calm down); link to the incident if `open_incident_id`.
- Vault status (`data-testid="vault-status"`): "Deposits PAUSED" (red) or "Deposits open" (green) depending on `vault.deposits_paused`; `idle_balances` balances in readable units (decimals taken from `state.tokens` by symbol).
- rsETH backing card (`data-testid="backing-card"`): token with `backing_ratio_bps !== null`; big figure `formatBpsPct` (`19.4%`), tone `backingTone`, subtitle `"1,200 WETH backing for 6,200 rsETH supply"` (`formatUnits(backing)` and `formatUnits(total_supply)`).
- Positions table (one row `data-testid="position-row"` per position with `supplied !== "0"`): deployment, asset, "Supplied" (`formatUnits` with the decimals of the matching reserve), "Value" (`value_usd`), "Withdrawable now" + bar of `withdrawable_ratio_bps` (`data-tone` = `withdrawableTone`). Empty list → message `"No open positions: all funds are back in the vault."` (expected case after fixture regeneration, where all positions are withdrawn).
- Reserves table (one row `data-testid="reserve-row"` per entry of `state.reserves`, grouped by deployment): asset, role (`borrowable` and `ltv_bps > 0` → "Lending + collateral, LTV 80.0%" for USDC and WETH; `ltv_bps > 0` only → "Collateral only, LTV 75.0%" for rsETH; `borrowable` only → "Lending"), "Collateral deposited" (`total_collateral`, balance separate from lendable liquidity, 2.2), "Utilization" (bar, `utilizationTone`), "Available liquidity" (units + USD value = `unitsToNumber × price_usd`), "Supply APY", "Borrow APY", `FROZEN` / `PAUSED` badges.

**9. Charts page (`/charts`, `pages/Charts.tsx`, `lib/chart.ts`).**
- Reserve selector: `borrowable` reserves of `state.reserves`, value `"<deployment_id>:<asset>"`, default `lend-eth:WETH`; stored in the URL (`?reserve=lend-eth:WETH`).
- `toChartPoints(points: SeriesPoint[], decimals: number)` → `{block, utilization, liquidity, withdrawable, apy, backing}` in % or in units (`null` kept, `connectNulls={false}`: the "withdrawable" line stops when the position is withdrawn, with the note "position closed").
- 5 charts (`data-testid="chart-utilization" | "chart-liquidity" | "chart-withdrawable" | "chart-apy" | "chart-backing"`), `XAxis type="number" dataKey="block" domain={['dataMin','dataMax']}`, dashed horizontal threshold lines: utilization 90% and 98%, withdrawable 80% and 50%, backing 99%.
- Alert markers: `alertsForReserve(alerts, dep, asset, minBlock, maxBlock): Alert[]` = alerts whose `deployment_id === null` (global, e.g. R1) **or** `deployment_id === dep`, and whose `block_number` is within the series' `[minBlock, maxBlock]`. Each alert gives a `ReferenceLine x={block_number}` with `className="alert-marker"`, severity colour, label `R1`..`R5` (prefix of `rule_id`); solid line if `asset === asset` selected, dashed otherwise. Below the charts, an "Events on this chart" list (one `li data-testid="alert-marker-item"` per alert: block, severity, title).

**10. Alerts & decisions page (`/alerts`, `pages/Alerts.tsx`).**
- Single feed: alerts and decisions sorted by descending `block_number`; at equal block, the decision above its alerts.
- Alert card (`data-testid="alert-card"`): severity badge, `RULE_LABELS[rule_id]`, `title`, `explanation` (in full, normal font), deployment/asset, block and `formatUtc(block_time)`, "Exposure" `formatUsd(exposure_usd)`.
- Decision card (`data-testid="decision-card"`): severity, `rationale`, `matrix_cell` in small text, "Exposure" and "Withdrawable", actions table: label, `AUTO` / `HUMAN` badge, status, amount (`formatUnits(amount, decimals of params.asset)`), `TxLink` transaction link.
- `components/TxLink.tsx`: `href = \`${__EXPLORER_URL__}/tx/${hash}\``, `target="_blank" rel="noreferrer"`, text `shortHash(hash)`; if `state.network === 'local'`, short hash without link (title "local chain: no explorer").
- For each `pending_approval` action: **Approve** and **Reject** buttons (`data-testid="approve-<decisionId>-<index>"`, `reject-…`) → `api.approve(decision.id, {action_index: index, approver: operatorName, approve: true|false})`; buttons disabled during the request; success → `refresh()` of decisions; `ApiError` → red message with `detail`.

**11. Incident & DORA page (`/incident`, `pages/Incident.tsx`).**
- Displayed incident: `state.open_incident_id`, otherwise the most recent from `api.incidents()`; none → "No incident so far.".
- Header: `title`, status badge (`open` red, `contained` amber, `resolved` green), severity, "Saved" `formatUsd(saved_usd)` large in green, "Still at risk" `formatUsd(at_risk_usd)` large in red if > 0, "Time to contain" = `contained_at - detected_at` in seconds.
- Timeline: `timeline` sorted by `at`, one row per event (UTC time, block, `kind` as a badge, `text`, `ref` clickable if it is a hash).
- DORA (if `dora`): `MAJOR INCIDENT` badge if `is_major`, `legal_basis`, `thresholds_met` bullets (official source). Criteria table (static data `CRITERIA_ROWS`: field, label, displayed threshold, e.g. "Clients affected | 100.0% | > 10% (Art. 9(1)(a))"; one row per `DoraCriteria` field, i.e. 14 with the three optional fields of 2.6: `counterparts_affected_pct` "Financial counterparts affected", `transactions_affected_count_pct` "Transactions affected (count)", `relevant_clients_affected` "Relevant clients or counterparts affected"). Field missing from the response (old fixture) → cell `—`, no crash.
- Deadlines (`data-testid="deadline-initial" | "deadline-intermediate" | "deadline-final"`): UTC date + `formatCountdown(due, useNow())`, red if past.
- Report: `react-markdown` + `remark-gfm`, **without** `rehype-raw` (the text may come from an LLM: no raw HTML). Box "AI-drafted sections, human review required: …" if `ai_drafted_sections` is not empty.
- **Submit to regulator** button (`data-testid="submit-incident"`): `window.confirm`, then `api.submitIncident(id, operatorName)`; disabled and replaced by "Submitted by X at Y" if `dora.submitted`.

**12. Evidence page (`/evidence`).** Decisions table: id, block, severity, `record_hash` (short), "Anchored on-chain" (`TxLink(anchor_tx)` + block, or "not anchored yet"), **Verify** button (`data-testid="verify-<id>"`) → `api.verify(id)`. Result (`data-testid="verify-result"`, attribute `data-result="match" | "mismatch"`): `MATCH` on green background + "Record matches its stored fingerprint" + stored/recomputed hash; `MISMATCH` on red background + `diffs` list. If `anchored` is false: amber note "not anchored". Copyable help line: `make verify ID=<id>`.

**13. Third-party dependencies page (`/dependencies`).** Title "Third-party register (DORA Art. 28)". Table sorted by criticality (critical, important, standard): name, kind, provider, criticality (badge), supports (bullets), fallback, status (coloured dot + word: ok, degraded, down, unknown).

**14. Metrics page (`/metrics`).** Units from 2.6, not to be confused: `*_rate` are fractions from 0 to 1 (displayed `× 100` as %), `*_pct_*` are **already** from 0 to 100 (displayed as is with `%`), `ttd_blocks_p50` / `ttd_blocks_p90` are `-1` when nothing is detected. Pure helpers in `lib/format.ts`: `formatRate(0.95) === '95.0%'`, `formatPct(87.5) === '87.5%'`, `formatTtd(-1) === 'not detected'`, `formatTtd(1) === '1 block'`, `formatTtd(3) === '3 blocks'`. Cards: "Detection rate" (`formatRate(detection_rate)`), "False positive rate" (`formatRate`), "Time to detect" p50/p90 (`formatTtd`), "Saved with us" vs "Saved without us" (`formatPct(saved_pct_mean)` and `formatPct(baseline_saved_pct_mean)`, small 2-bar `BarChart` on a 0..100 scale), "Runs" (`runs_attack` / `runs_normal`). `mainnet_replay === null` → card "Mainnet replay: phase 2". `notes` as a list, `rules_version` short. `runs_attack === 0` → banner "No evaluation run yet (fixture values)". The `synthetic` keys are read with a fallback (`?? '—'`): no crash if T7 adds or removes some.

**15. Demo page (`/demo`).**
- "Variant" selector (`data-testid="variant-select"`): `default` "Default attack (fast drain)", `slow` "Slow drain", `usdc` "USDC market drained"; default `default`.
- Optional "Seed" field (integer from 0 to 999999; `0` = default parameters, no randomness, useful for a reproducible demo; out of range → validation message, nothing sent).
- **Launch attack** button (`data-testid="launch-attack"`): if the field is empty, `seed = Math.floor(Math.random() * 999_999) + 1` (integer in [1, 999999]); the front end **always** sends an integer, never `null`; display `Seed <n>` **before** sending; `api.demoAttack(seed, variant)`; then poll `api.demoRun(run_id)` every 2 s while `status === 'running'`. Display the `seed` and `variant` **returned** by the backend (they are authoritative). 409 "run already running" → amber message and resume polling the current run if its id is known.
- **Reset** button (`data-testid="reset-demo"`): `window.confirm('Redeploy contracts and clear all alerts?')` then `api.demoReset()`.
- Run panel: `run_id`, `kind`, `status` (badge), `params`, `log` in monospace, auto-scroll to the last line. In fixture mode: note "Fixture mode: nothing happens on chain".

#### Tests that must pass

Global command: `make test-t6`. Component tests render the page inside a `MemoryRouter`; the network is simulated with `vi.stubGlobal('fetch', vi.fn(...))` returning `new Response(JSON.stringify(x), {status: 200})`; the mode is chosen with `vi.stubEnv('VITE_USE_FIXTURES', 'true' | 'false')`. Recharts draws nothing under jsdom without a size: in chart tests, `vi.mock('recharts', ...)` replaces `ResponsiveContainer` with a render at `width=800 height=240` (cloneElement of the child).

- **T6-01 · typecheck.** `cd frontend && npm run typecheck` → code 0, no errors.
- **T6-02 · build.** `cd frontend && npm run build` → code 0, `frontend/dist/index.html` exists; `grep -rE "_PK|PRIVATE" frontend/dist` finds nothing.
- **T6-03 · formatting** (`src/lib/format.test.ts`): `formatUsd(1325000) === '$1,325,000'`, `formatUsd(0) === '$0'`; `formatUnits('1850000000000000000000', 18) === '1,850'`, `formatUnits('400000000000', 6) === '400,000'`, `formatUnits('1500000000000000000', 18) === '1.5'`; `formatBpsPct(1935) === '19.4%'`, `formatBpsPct(10000) === '100.0%'`; `withdrawableTone(8000) === 'ok'`, `(7999) === 'warn'`, `(5000) === 'warn'`, `(4999) === 'bad'`; `utilizationTone(9800) === 'bad'`; `shortHash('0x433c5ce05750d9c9189b632954beb23cccdbf172c5556778a026ccf10a6f74cc') === '0x433c…74cc'`; `formatCountdown('2026-10-11T12:02:27Z', Date.parse('2026-10-11T08:02:27Z')) === '4 h 00 min left'`; `formatCountdown('2026-10-11T07:00:00Z', Date.parse('2026-10-11T08:05:00Z')) === 'overdue by 1 h 05 min'`; `formatRate(0.95) === '95.0%'`, `formatRate(0) === '0.0%'`; `formatPct(87.5) === '87.5%'`; `formatTtd(-1) === 'not detected'`, `formatTtd(3) === '3 blocks'`.
- **T6-04 · polling** (`src/hooks/usePolling.test.ts`, `vi.useFakeTimers()`, `renderHook`): `test_calls_immediately_then_every_2s` → 1 call on mount, 3 after `await vi.advanceTimersByTimeAsync(4000)`; `test_no_overlap` → fetcher that never resolves: only 1 call after 10 s; `test_keeps_data_on_error` → success `{a:1}` then rejection: `data` stays `{a:1}`, `error` set; `test_stops_on_unmount` → 0 calls after unmount.
- **T6-05 · API client** (`src/api.test.ts`): `test_fixture_mode_no_fetch` → `VITE_USE_FIXTURES=true`, `await api.state()` returns `block_number` equal to that of `fixtures/state.json`, `fetch` never called; `test_series_url` → real mode, `api.series('lend-eth', 'WETH', 300)` calls `http://localhost:8000/api/series?deployment_id=lend-eth&asset=WETH&limit=300`; `test_404_raises` → 404 response `{"detail":"decision not found"}`: `api.verify('X')` rejects with `ApiError` (`status 404`, `detail 'decision not found'`); `test_fixture_series_key` → fixture mode, `api.series('lend-eth','WETH')` returns 41 points (series from `series.json`, `limit` 300); `test_503_no_snapshot` → 503 response `{"detail":"no snapshot yet"}`: `api.state()` rejects with `ApiError` status 503 and `isNoSnapshotYet(err) === true`; `test_demo_attack_body` → `api.demoAttack(7, 'slow')` posts exactly `{"seed":7,"variant":"slow"}`.
- **T6-06 · Overview from fixtures** (`src/pages/Overview.test.tsx`, fixture mode): `total-value` contains `$1,325,000` (invariant 2.2: 250 WETH × $2,500 + 700,000 USDC); `total-withdrawable`, `total-idle`, `total-at-risk` contain `formatUsd()` of the values read from `fixtures/state.json`; `risk-badge` has the text `CRITICAL`; `vault-status` contains `PAUSED`; `backing-card` contains `19.4%` (1,200 / 6,200); number of `reserve-row` = 6; number of `position-row` = number of fixture positions with `supplied !== "0"`.
- **T6-07 · Overview with no position and waiting**: simulated fetch returning `state.json` with `positions: []` → text `No open positions: all funds are back in the vault.` and 0 `position-row`; `test_waiting_first_block` → fetch of `/api/state` returning 503 `{"detail":"no snapshot yet"}`: `waiting-first-block` visible with the text `Waiting for first block`, no `total-value` card, no `Backend unreachable` banner.
- **T6-08 · withdrawable bar colours**: inline state with 3 positions at `withdrawable_ratio_bps` 10000, 7000, 4000 → bars with `data-tone` `ok`, `warn`, `bad` and `aria-valuenow` 100, 70, 40.
- **T6-09 · alert markers** (`src/pages/Charts.test.tsx`): series = `series.json["lend-eth:WETH"]` (blocks 45201800 to 45201880); inline alerts: global R1 at block 45201812 (`deployment_id: null`), R2 `lend-eth`/`WETH` at 45201835, R3 `lend-avax`/`WETH` at 45201850, R4 `lend-eth`/`WETH` at 45209999 (outside the window). Expected: `alertsForReserve(...)` returns 2 alerts; 2 `alert-marker-item`; in `chart-utilization`, `querySelectorAll('.alert-marker').length === 2`.
- **T6-10 · alerts and decisions feed** (`src/pages/Alerts.test.tsx`): `test_newest_first` → inline alerts at blocks 10, 30, 20: displayed order 30, 20, 10; `test_approve_posts_body` → `localStorage['sh.operator'] = 'jury-demo'`, inline decision `DEC-fuji-45201812-1` with actions `[NOTIFY executed, PAUSE_DEPOSITS executed, UNPAUSE_DEPOSITS human pending_approval]`, click on `approve-DEC-fuji-45201812-1-2` → `fetch` called with `http://localhost:8000/api/decisions/DEC-fuji-45201812-1/approve`, `method: 'POST'`, JSON body exactly `{"action_index":2,"approver":"jury-demo","approve":true}`; `test_reject_posts_false` → same with `approve: false`; `test_tx_link` → action with `tx_hash` `0x8a1f…e8d7`: link `href === 'https://testnet.snowtrace.io/tx/0x8a1f0c3d9e7b6a5f4e3d2c1b0a9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7'`.
- **T6-11 · Verify** (`src/pages/Evidence.test.tsx`): `test_verify_match_from_fixture` → fixture mode, click on the Verify button of the first decision: `verify-result` has `data-result="match"` and the text `MATCH`; `test_verify_mismatch` → fetch returns `{...verify.json, match: false, recomputed_hash: '0xdead…', diffs: ['actions[2].status: stored executed, recomputed failed']}`: `data-result="mismatch"`, text `MISMATCH`, the diff line is visible.
- **T6-12 · Incident and DORA** (`src/pages/Incident.test.tsx`, fixture mode, `vi.setSystemTime(dora.classified_at)` from the fixture): `deadline-initial` contains `4 h 00 min left`; the report is rendered as HTML (an `h1` containing `DORA`); `test_submit_posts_body` → real mode, click on `submit-incident` (confirm mocked to `true`): `POST /api/incidents/INC-20261011-001/submit` with body `{"submitted_by":"jury-demo"}`.
- **T6-13 · Demo** (`src/pages/Demo.test.tsx`): `vi.spyOn(Math, 'random').mockReturnValue(0.004242)` → text `Seed 4242` displayed (`Math.floor(0.004242 × 999999) + 1`), `POST /api/demo/attack` with body `{"seed":4242,"variant":"default"}`, then `GET /api/demo/runs/<returned run_id>` called; the response's `log` lines are displayed; `test_variant_and_seed_zero` → select `usdc` in `variant-select` and Seed field at `0`: body exactly `{"seed":0,"variant":"usdc"}`; `test_seed_range` → `Math.random` mocked to `0` then to `0.9999999`: seeds sent `1` and `999999` (never `0` or `null` when the field is empty); `test_409_running` → 409 response `{"detail":"demo run already running"}`: message visible, no exception.
- **T6-14 · fixture mode without backend** (`src/App.test.tsx`): `VITE_USE_FIXTURES=true`, `fetch = vi.fn(() => Promise.reject(new Error('no backend')))`, render `<App/>` on `/` → `FIXTURE MODE` banner present, `total-value` contains `$1,325,000`, `fetch` called 0 times; navigation to the 8 routes without exceptions.
- **T6-15 · types/fixtures conformance** (`src/types.contract.test.ts`): for `StateResponse`, `Alert`, `Decision`, `Action`, `Incident`, `VerifyResult`, `DemoRun`, `EvalMetrics`, a constant `const STATE_KEYS: Record<keyof StateResponse, true> = {...}` (the compiler rejects an extra or missing key); at runtime, `Object.keys(fixture).sort()` equals `Object.keys(STATE_KEYS).sort()` (all keys are always present, 2.5). Types are imported from `src/types.ts` (T0); until T0 has delivered it, from the local copy `src/test/types.local.ts` (tests only), to be switched back as soon as it is delivered. Detects any drift between `models.py` (via the regenerated fixtures) and `types.ts`; on failure, ask T0 via `docs/contract-requests.md`, do not fix `types.ts` yourself.
- **T6-16 · manual smoke test against the T0 skeleton.** `make backend` (`USE_FIXTURES=true`) then `VITE_USE_FIXTURES=false make frontend`: the 8 pages render, the network tab shows `/api/state`, `/api/alerts`, `/api/decisions`, `/api/health` every 2 s, no console errors, no CORS errors.

#### Definition of done

- [ ] `make test-t6` green (T6-01 to T6-15) on a clean machine after `make setup`.
- [ ] T6-16 done against the T0 skeleton, then redone against the real backend as soon as T3/T4/T5 are delivered.
- [ ] Application code imports only `src/types.ts` (delivered by T0, never modified by T6); no local type copy left outside `src/test/`; any divergence reported in `docs/contract-requests.md`.
- [ ] Production build tested with empty `VITE_API_URL`: calls go out relative to `/api/...` (same origin, T8's nginx).
- [ ] "Waiting for first block" shown at `make demo` startup as long as the API answers 503, then replaced by the data without reloading.
- [ ] The 8 routes exist and are readable on a 1920×1080 projector without zoom; Overview fits without horizontal scrolling.
- [ ] No base-unit amount converted to `Number` outside `unitsToNumber` (charts).
- [ ] No `D1..D7` rule id in the code; no French text in the UI.
- [ ] The build contains no root `.env` variable except `EXPLORER_URL`.
- [ ] `frontend/.env.example` and `mk/t6.mk` committed; `make frontend` and `make frontend-build` work from the root.
- [ ] Screenshots of the 8 pages (fixture mode) attached to the PR for T9.

#### Known pitfalls

- **Recharts under jsdom**: `ResponsiveContainer` measures 0 px and draws nothing. Mock `ResponsiveContainer` in tests (see above) and polyfill `ResizeObserver`.
- **Categorical X axis**: a `ReferenceLine x=45201811` is ignored if 45201811 is not a point of the series (series have a point every 2 blocks). Always `XAxis type="number"`.
- **BigInt**: `Number("1850000000000000000000")` loses precision; `formatUnits` works in `BigInt`. Target ES2020 minimum in `tsconfig`.
- **JSON imports**: TS infers `network: string`, not `'fuji'`; cast `as unknown as StateResponse`. Fixtures are outside `frontend/`: alias + `server.fs.allow`.
- **Secret leaks**: never set `envPrefix: ''` or `envDir: '..'` with a broad prefix; only `EXPLORER_URL` is injected via `define`.
- **Fake timers + promises**: use `await vi.advanceTimersByTimeAsync()` (not the synchronous version), otherwise mocked `fetch` calls do not resolve.
- **StrictMode**: in dev effects run twice; without cleaning up the `setTimeout` you poll twice.
- **Stale then regenerated fixtures**: after regeneration, all positions are withdrawn (empty positions or `supplied: "0"`), `pending_approval` actions change index. Hard-code nothing on these values; tests use inline objects or the invariants ($1,325,000, 19.4%, `CRITICAL`).
- **Explorer link locally**: on anvil, snowtrace does not know the transactions; show the hash without a link when `network === 'local'`.
- **Time zone**: display UTC explicitly; the jury is in Paris (UTC+2), an implicit local time creates inconsistencies with the incident timeline.
- **Report markdown**: never raw HTML (`rehype-raw` forbidden), the text may come from Bedrock.
- **Approve then polling**: do not update local state optimistically, re-read `GET /api/decisions` (otherwise the next poll overwrites the display and the status flickers).
- **CORS**: the API is `*` (2.9); if a CORS error appears, it is almost always a wrong `VITE_API_URL` (port or `http`/`https`).
- **`VITE_API_URL` in production**: the variable is frozen at build time. Do not build with `http://localhost:8000` for EC2 (the jury's browser would call its own machine): leave it empty, `API_URL` is then `''` and calls are relative. Watch out for `??`: a variable that is defined but empty does give `''` (intended), not the dev default.
- **503 at startup**: right after `make demo` or a reset, `/api/state` answers 503 `no snapshot yet` for a few blocks. Do not show it as a red outage, do not stop polling.
- **Metric units**: `detection_rate` 0.95 → `95.0%` but `saved_pct_mean` 95 → `95.0%` (not `9500%`); `ttd_blocks_p50 = -1` → `not detected` (not `-1 blocks`).
- **`risk_level` going back down**: it only reflects conditions still true at the latest snapshot; after full withdrawal it can drop back to `INFO` while the incident stays open. Do not infer incident severity from `risk_level`.

#### Later (phase 2)

- Server-Sent Events or WebSocket instead of polling; incremental loading of alerts with `since_block`.
- Additional charts (phase 2 indicators: bait APY, collateral concentration, contagion between deployments), multi-reserve comparison on the same chart.
- Several simultaneous incidents, filters and search in the alert feed.
- Authentication and roles for Approve/Submit (signature by the Safe signers), operator log.
- PDF export of the DORA report, CSV export of the third-party register.
- Playwright end-to-end tests on `make demo`, dark mode, mobile version, internationalisation.

#### Claude Code starter prompt

```
You are working on task T6 (Dashboard) of the TASKS.md file at the root of the repo.
1. Read TASKS.md sections 1 and 2 in full, then section T6 in full, then backend/models.py,
   frontend/src/types.ts (T0) and the files fixtures/state.json, fixtures/series.json, fixtures/verify.json, fixtures/demo_run.json.
   Warning: alerts.json, decisions.json, incident.json, state.json and series.json are stale
   (ids D1..D7) and will be regenerated: hard-code nothing based on their content.
2. Modify ONLY the files listed in T6's "Owned files" (frontend/ except src/types.ts,
   and mk/t6.mk; never redefine NETWORK in mk/t6.mk).
   frontend/src/types.ts belongs to T0: do not create it and do not modify it. If it is missing or diverges,
   write the request in docs/contract-requests.md, tell me, and meanwhile use a local copy
   src/test/types.local.ts only in tests.
   Any other change request (contract, routes, fixtures, root .env.example): do not edit,
   write it in docs/contract-requests.md and tell me.
3. Work first in VITE_USE_FIXTURES=true mode (no backend), then against the T0 skeleton
   (make backend, USE_FIXTURES=true). Do not wait for any other task.
4. Start by writing tests T6-03 to T6-15 (vitest + Testing Library) with the given names and paths,
   then the code, page by page in this order: format/labels, api + fixtureDb, usePolling, Layout,
   Overview, Alerts, Evidence, Incident, Charts, Demo, Dependencies, Metrics.
5. Before each commit: make test-t6 must be green (typecheck, build, vitest). Small commits,
   push often after each green test.
   Contract points not to miss: API_URL = VITE_API_URL ?? (DEV ? 'http://localhost:8000' : '');
   503 "no snapshot yet" → "Waiting for first block"; *_rate in 0..1, *_pct_* in 0..100,
   ttd -1 → "not detected"; variants default|slow|usdc; random seed in [1, 999999], 0 = defaults.
6. UI in plain English, big numbers, colour is never the only information.
```


---
### T7 · Evaluation and metrics (simple version)

**Goal.** Measure, reproducibly and honestly, what the platform does on the scenario: does it detect the attack, in how many blocks, what share of the treasury it protects (compared with a passive treasury), and does it cry wolf on a normal day. The test harness runs N attacks and M normal days on the local chain, reads the API as a black box, and writes `data/eval/metrics.json` (served by `GET /api/metrics`, displayed by T6, cited by T9) and `data/eval/report.md`. Metrics stay **simple** in the MVP: 8 numbers, defined exactly below.

**Depends on.**
- T1 → local chain + `make deploy` + `deployments/local.json` + ABIs → meanwhile: not needed for unit tests; for anchoring, `--no-anchor`.
- T2 → `POST /api/demo/reset`, `POST /api/demo/attack`, `GET /api/demo/runs/{run_id}`, `make normal`, and the `RunRecord`s written to `data/runs/<run_id>.json` → meanwhile: hand-built `RunRecord`s in the tests (with the 4 treasury positions, like the contract's `RunRecord` and the regenerated `fixtures/run_record.example.json`) and a `FakeApi` (step 6).
- T3 → `GET /api/health`, `GET /api/alerts`, `GET /api/series`, `GET /api/state`, `backend/config/rules.yaml` → meanwhile: hand-built `Alert` lists, `rules.yaml` content copied from 2.7 into a temporary file.
- T4 → `GET /api/decisions` with `EMERGENCY_WITHDRAW` `executed` actions and their `amount` → meanwhile: hand-built `Decision` lists.

**Unblocks.** T6 ("Evaluation" card on the dashboard via `GET /api/metrics`), T9 (numbers in the README, the deck, the defense sheet, the `report.md` table).

**Owned files.** `evaluation/metrics.py`, `evaluation/run_synthetic.py`, `evaluation/report.py`, `evaluation/api_client.py`, `backend/api/metrics.py`, `mk/t7.mk`, `backend/tests/test_t7_*.py` (`evaluation/__init__.py` belongs to T0). Generated files (written at runtime): `data/eval/metrics.json` and `data/eval/report.md` (**committed**: T0's `.gitignore` makes the exception), `data/eval/runs.jsonl`, `data/eval/rules_frozen.json` (not committed).

**Read before starting.** TASKS.md sections 1.2 (scenario), 1.5 (file ownership), 2.2 (initial deployment parameters, `EvidenceRegistry`), 2.4 (helpers), 2.5 (conventions), 2.6 (`RunRecord`, `EvalMetrics` and its units, `StateResponse` totals), 2.7 (rules), 2.8 (matrix), 2.9 (API, error codes), 2.10 (maintenance mode), 2.11 (`make`), 4.2 (E2E-1); `backend/models.py` (`Alert`, `Decision`, `Action`, `RunRecord`, `EvalMetrics`, `SeriesPoint`, `Health`, `DemoRun`); `backend/api/metrics.py`; `fixtures/snapshots_attack.jsonl`, `fixtures/snapshots_normal.jsonl`.

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Ground truth of a run | `data/runs/<run_id>.json` → `RunRecord` (`label`, `variant`, `seed`, `start_block`, `end_block`, `attack_start_block`, `phase_blocks`, `treasury_supplied_at_start` with the 4 treasury positions) | T2 | hand-built `RunRecord` in the tests (4 positions, see T7-04) |
| Launching an attack | `POST /api/demo/attack {"seed": int, "variant": "default"\|"slow"\|"usdc"}` → `DemoRun`; tracked via `GET /api/demo/runs/{run_id}`. The harness always sends an integer seed ≥ 1 (never `null`, randomly drawn by the backend, nor `0`, deterministic default parameters). 409 if a demo run is already in progress | T2 | `FakeApi` (step 6) |
| Launching a normal day | `make normal MINUTES=<m> SEED=<s>` (blocking, writes a `RunRecord` `label="normal"`) | T2 | `FakeApi.run_normal()` |
| Reset | `POST /api/demo/reset` → `DemoRun` (`kind="reset"`) | T2 | `FakeApi.reset()` |
| Backend health | `GET /api/health` → `Health` (`network`, `block_number`, `engine_running`) | T3 | `FakeApi.health()` (block advances by 1 on each call) |
| Alerts | `GET /api/alerts?since_block=<start_block>` → `Alert[]` | T3 | hand-built `Alert` lists; later replay of the `.jsonl` via `Engine.process` (T7-16) |
| Decisions | `GET /api/decisions` → `Decision[]` | T4 | hand-built `Decision` lists |
| Liquidity per reserve | `GET /api/series?deployment_id=…&asset=…&limit=2000` → `SeriesPoint[]` | T3 | the two `.jsonl` converted into series (T7-08) |
| Prices and decimals | `GET /api/state` → `reserves[].price_usd`, `reserves[].decimals`, `vault.idle_balances`, `totals.idle_usd` (= Σ vault balances × price, 2.6); 503 `no snapshot yet` until the engine has read a block | T3 | constants from 2.2: USDC $1.00 / 6 dec., WETH $2,500 / 18 dec., rsETH $2,500 / 18 dec. |
| Frozen thresholds | exact bytes of `backend/config/rules.yaml` | T3 | temporary file with the YAML from 2.7 |
| Evidence registry | `EvidenceRegistry.anchor(bytes32, "rules", uri)` via `backend.chain` | T1 (contract), T0 (helpers) | `--no-anchor` |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `data/eval/metrics.json` (committed) | `EvalMetrics` (units from 2.6, all keys present, `null` if empty): `generated_at`, `rules_version` (`"sha256:<64 hex>"`), `synthetic` with **exactly** the 8 keys `runs_attack` (int), `runs_normal` (int), `detection_rate` (float 0..1, 3 decimals), `false_positive_rate` (float 0..1, 3 decimals), `ttd_blocks_p50` (int, -1 if no detection), `ttd_blocks_p90` (int, -1 likewise), `saved_pct_mean` (float 0..100, 1 decimal), `baseline_saved_pct_mean` (float 0..100, 1 decimal); `mainnet_replay: null`; `notes: list[str]` | T6, T9, `GET /api/metrics` |
| `data/eval/report.md` (committed) | markdown, step 5 template | T9 |
| `data/eval/runs.jsonl` | one JSON line per run (serialized `AttackRunResult` or `NormalRunResult`, with `"kind"`) | `make eval-report`, T9 |
| `data/eval/rules_frozen.json` | `{"rules_version": "sha256:…", "frozen_at": "<ISO>", "anchor_tx": "0x…"\|null, "anchor_block": int\|null, "network": "local"}` | T9 (evidence of the freeze) |
| `GET /api/metrics` | `EvalMetrics` (file if present and valid, otherwise fixture) | T6 |
| `make eval`, `make eval-report`, `make test-t7`, `make test-t7-e2e` | targets in `mk/t7.mk` | everyone |

#### Detailed specification

**1. Definitions (copy as is at the top of `evaluation/metrics.py`).**
- *Run window*: blocks `[record.start_block, record.end_block + settle_blocks]` (`settle_blocks` = 10 by default). Any alert or decision outside the window is ignored.
- *Detected* (attack run): there is at least one alert `severity == "critical"` with `attack_start_block <= block_number <= end_block + settle_blocks`.
- *TTD* (`ttd_blocks`): `block_number` of the first such alert − `attack_start_block` (integer ≥ 0). `None` if not detected. On the regenerated fixture, the forged mint is visible in the snapshot of block 45,201,812 and the R1 alert carries that same block (as does decision `DEC-fuji-45201812-1`) → TTD = 0 in replay. Live, the engine may read the next block: TTD from 0 to 2.
- *Affected positions*: all keys of `record.treasury_supplied_at_start` (`"<deployment>:<asset>"`). In the MVP, both deployments accept rsETH as collateral, so R1 affects **all 4 positions**: `lend-eth:WETH` 150 ($375,000), `lend-eth:USDC` 400,000 ($400,000), `lend-avax:WETH` 100 ($250,000), `lend-avax:USDC` 300,000 ($300,000); total **$1,325,000**.
- *Start value*: `Σ int(supplied) / 10**decimals[asset] * price[asset]` over the affected positions.
- *Saved value*: sum, over the decisions in the window, of actions with `type == "EMERGENCY_WITHDRAW"` **and** `status == "executed"` **and** non-zero `amount` **and** a `tx_hash` that does not start with `0xdry`, of `int(amount) / 10**decimals * price`, the position key being `f'{params["deployment_id"]}:{params["asset"]}'`. Per position, the counted amount is capped at `treasury_supplied_at_start[key]` (no double counting). Statuses `planned`, `skipped`, `failed`, `pending_approval`, `approved`, `rejected` do not count. An `executed` action whose `tx_hash` starts with `0xdry` (executed in dry-run, no funds moved) is excluded from the saved value, with a warning and a note `"dry-run withdrawals excluded from saved: <run_id>"`. An `EMERGENCY_WITHDRAW` that returns 0 (nothing to withdraw) has `amount = "0"`: it does not count. An `EMERGENCY_WITHDRAW` that reverts (`"MiniLend: paused"`) is `failed`: it does not count.
- *`saved_pct`* = `100 * saved value / start value` (0.0 if start value = 0, with a note).
- *`baseline_saved_pct`* (passive treasury that does not move): a position whose reserve reached zero available liquidity during the window is worth 0%; the others are worth 100%. Result = `100 * value of non-drained positions / start value`. `default` attack (drained reserve `lend-eth:WETH`) → **71.7**; `usdc` variant (drained reserve `lend-eth:USDC`) → **69.8**; no drained reserve → 100.0.
- *False positive* (normal run): at least one alert `severity ∈ {"high", "critical"}` in the window.
- *Percentile*: nearest rank, `sorted(v)[ceil(p/100 * len(v)) - 1]`, computed on the TTDs of detected runs only.
- *Means* `saved_pct_mean` and `baseline_saved_pct_mean`: over **all** valid attack runs, misses included (a miss counts with what it actually saved).

**2. `evaluation/metrics.py` (pure: no I/O, no network).**
```python
SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
DEFAULT_PRICES = {"USDC": 1.0, "WETH": 2500.0, "rsETH": 2500.0}
DEFAULT_DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}
SYNTHETIC_KEYS = ("runs_attack", "runs_normal", "detection_rate", "false_positive_rate",
                  "ttd_blocks_p50", "ttd_blocks_p90", "saved_pct_mean", "baseline_saved_pct_mean")

@dataclass
class AttackRunResult:
    run_id: str; variant: str; seed: int; attack_start_block: int
    detected: bool; first_critical_block: int | None; first_rule_id: str | None; ttd_blocks: int | None
    start_value_usd: float; saved_usd: float; saved_pct: float; baseline_saved_pct: float
    drained_keys: list[str]; pre_attack_alerts: int          # alerts >= high BEFORE attack_start_block
    warnings: list[str] = field(default_factory=list)       # e.g. "no executed EMERGENCY_WITHDRAW"

@dataclass
class NormalRunResult:
    run_id: str; seed: int; false_positive: bool; high_alert_ids: list[str]; max_severity: str

def in_window(block: int, record: RunRecord, settle_blocks: int = 10) -> bool
def first_critical_after(alerts: list[Alert], record: RunRecord, settle_blocks: int = 10) -> Alert | None
def ttd_blocks(alerts, record, settle_blocks=10) -> int | None
def start_values_usd(record, prices=DEFAULT_PRICES, decimals=DEFAULT_DECIMALS) -> dict[str, float]
def saved_usd(decisions: list[Decision], record, prices=..., decimals=..., settle_blocks=10) -> float
def baseline_saved_pct(record, drained_keys: set[str], prices=..., decimals=...) -> float
def drained_keys_from_series(series: dict[str, list[SeriesPoint]], record, settle_blocks=10) -> set[str]
def percentile(values: list[int], p: float) -> int           # ValueError if values is empty
def evaluate_attack(record, alerts, decisions, drained_keys, prices=..., decimals=..., settle_blocks=10) -> AttackRunResult
def evaluate_normal(record, alerts, settle_blocks=10) -> NormalRunResult
def rules_version_of(path: Path) -> str                      # "sha256:" + sha256(exact file bytes)
def aggregate(attacks: list[AttackRunResult], normals: list[NormalRunResult], rules_version: str,
              notes: list[str], now: datetime | None = None) -> EvalMetrics
```
Details:
- An `Action` without `params["deployment_id"]` or `params["asset"]` → ignored + warning `"EMERGENCY_WITHDRAW without deployment_id/asset in <decision_id>"`.
- An action key missing from `treasury_supplied_at_start` → ignored + warning.
- An `executed` action with `tx_hash.startswith("0xdry")` → ignored + warning `"dry-run EMERGENCY_WITHDRAW excluded in <decision_id>"` (the harness adds the matching run note).
- `drained_keys_from_series`: key drained if a point with `start_block <= block_number <= end_block + settle` has `int(available_liquidity) == 0`.
- `aggregate`: `detection_rate = detected / runs_attack` (0.0 if no run); `false_positive_rate = fp / runs_normal`; rates rounded to 3 decimals in 0..1, percentages rounded to 1 decimal in 0..100 (2.6); if no run is detected, `ttd_blocks_p50 = ttd_blocks_p90 = -1` and note `"no detected attack run: ttd undefined"`. Adds to the notes one line per miss (`"MISS <run_id> variant=<v> seed=<s>: no critical alert in window"`) and per false positive (`"FALSE POSITIVE <run_id>: <alert ids>"`). Validates the output with `EvalMetrics.model_validate` before returning it.

**3. `evaluation/api_client.py`.** One interface, two implementations (the real one, and `FakeApi` in the tests):
```python
class EvalApi(Protocol):
    def health(self) -> Health
    def reset(self) -> DemoRun
    def attack(self, seed: int, variant: str) -> DemoRun
    def demo_run(self, run_id: str) -> DemoRun
    def run_normal(self, seed: int, minutes: int) -> str     # returns the run_id
    def alerts(self, since_block: int) -> list[Alert]
    def decisions(self) -> list[Decision]
    def series(self, deployment_id: str, asset: str) -> list[SeriesPoint]
    def state(self) -> StateResponse
    def run_record(self, run_id: str) -> RunRecord           # reads data/runs/<run_id>.json

class HttpEvalApi:   # httpx.Client(base_url=api, timeout=30)
```
`HttpEvalApi.run_normal`: lists `data/runs/*.json` beforehand, runs `subprocess.run(["make", "normal", f"MINUTES={m}", f"SEED={s}"], check=True)`, then takes the **new** file with `label == "normal"` (error if zero or several). Each response is validated with the Pydantic model (an invalid response = errored run, not a harness crash).

**4. `evaluation/run_synthetic.py` (the harness).**
```
python -m evaluation.run_synthetic --runs 10 --normal 3 --minutes 2 --settle-blocks 10 \
    --base-seed 1 --api http://127.0.0.1:8000 --out data/eval [--no-anchor]
```
`def run_eval(api: EvalApi, runs: int, normal: int, minutes: int, settle_blocks: int, base_seed: int, out_dir: Path, anchor: bool) -> EvalMetrics`

1. **Preflight.** `settings.NETWORK == "local"` otherwise exit 1 (`"eval runs on local only in the MVP"`). `GET /api/health`: `status == "ok"`, `network == "local"`, `engine_running == true`, otherwise exit 1 with the reminder: `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false make backend`. `backend/config/rules.yaml` must exist, otherwise exit 1.
2. **Threshold freeze (before the first run).** `frozen = rules_version_of(CONFIG_DIR / "rules.yaml")`. Writes `rules_frozen.json`. If `anchor`: after the first `reset` (the reset redeploys, so an earlier anchoring would be lost), call `chain.send(chain.registry().anchor(bytes.fromhex(hex), "rules", "repo://backend/config/rules.yaml"), chain.account("evidence"))` (if `registry()` does not exist yet in `chain.py`, use `chain.contract("EvidenceRegistry")`). Revert `"Evidence: already anchored"` → read `anchoredAt(hash)` and continue. Any other error → note `"rules hash not anchored: <reason>"`, continue. On local, anchoring is ephemeral: note it. Anchoring happens when no scenario is running (no nonce conflict with T4, which uses the same key).
3. **Attack loop** `i = 0..runs-1`: `seed = base_seed + i`, `variant = ("default", "slow", "usdc")[i % 3]`.
   a. `reset()`, then wait for `demo_run(reset.run_id).status == "done"` (poll 2 s, timeout 180 s) then `health()` ok with an advancing `block_number` (timeout 120 s). The reset sets `data/runtime/local/maintenance.flag` then removes it in a `finally` and increments `store.generation`: the engine evaluates no rule in the meantime and restarts from an empty window. If `reset()` or `attack()` returns 409 (demo run already in progress), wait 2 s and retry (timeout 180 s, then errored run). `state()` may return 503 `no snapshot yet` right after the reset: retry the same way.
   b. `prices, decimals, idle_before` ← `state()` (`idle_before` = `totals.idle_usd`, i.e. Σ vault balances × price; fall back to the constants if the call fails, with a warning).
   c. `run = attack(seed, variant)`; poll `demo_run(run.run_id)` every 2 s until `done` or `failed` (timeout 600 s).
   d. `record = run_record(run.run_id)`; wait for `health().block_number >= record.end_block + settle_blocks`.
   e. `alerts(since_block=record.start_block)`, `decisions()`, `series()` for each affected key, `state()` (for `idle_after` = `totals.idle_usd`).
   f. Drift check: any alert whose `rules_version != frozen` → abort, exit 3 (`"rules.yaml changed during evaluation"`).
   g. `drained = drained_keys_from_series(...)`; if the series are empty, fallback: if `"liquidity_zero" in record.phase_blocks`, `drained = {VARIANT_TARGET[variant]}` with `VARIANT_TARGET = {"default": "lend-eth:WETH", "slow": "lend-eth:WETH", "usdc": "lend-eth:USDC"}` + warning.
   h. `evaluate_attack(...)`. Cross-check: `idle_delta_usd` (idle after − before, valued) vs `saved_usd`; gap > 1% of the start value → warning. If detected but no `executed` `EMERGENCY_WITHDRAW` → warning `"no executed EMERGENCY_WITHDRAW"`. If a `0xdry…` `tx_hash` appears → excluded from the saved value and note `"dry-run withdrawals excluded from saved: <run_id> (backend must run with DRY_RUN_ACTIONS=false)"`.
   i. Append the line to `runs.jsonl` immediately (a crash does not lose runs already done). Log: `[eval] attack 3/10 seed=3 variant=usdc run=RUN-… detected=yes rule=R1_BACKING_DROP ttd=1 saved=100.0% baseline=69.8%`.
4. **Normal loop** `j = 0..normal-1`: `seed = 10_000 + base_seed + j`; reset as in 3a; `run_id = run_normal(seed, minutes)`; wait for `end_block + settle`; `evaluate_normal`. Log: `[eval] normal 1/3 seed=10001 run=RUN-… false_positive=no max_severity=warning`.
5. **Errored runs.** `DemoRun.status == "failed"`, timeout, missing or invalid `RunRecord` → "errored" run: excluded from rates, listed in the notes (`"ERRORED <run_id or seed>: <reason>"`) and in the report. Never silently rerun. If more than 20% of runs errored → metrics written anyway, exit 2.
6. **End.** `aggregate(...)` → `metrics.json` (atomic write: `.tmp` file then `os.replace`); `report.write_report(...)`. Systematic notes: `"network=local"`, `"variants: default x4, slow x3, usdc x3"`, `"settle_blocks=10"`, `"rules anchored: tx 0x… block N (local, ephemeral)"` or `"rules not anchored"`, `"thresholds frozen before first run; variants authored by T2 independently of rules.yaml"`.

**5. `evaluation/report.py`.** `def write_report(metrics: EvalMetrics, attacks: list[AttackRunResult], normals: list[NormalRunResult], errored: list[str], out: Path) -> None` and `python -m evaluation.report` (rereads `runs.jsonl` + `metrics.json`, rewrites `report.md`). Template:
```markdown
# Synthetic evaluation report
Generated <ISO 8601 UTC> · network local · rules sha256:09bf…2847 (anchored tx 0x… block 57)
## Summary
| Metric | Value |
|---|---|
| Attack runs | 10 |
| Detection rate | 100.0 % (10/10) |
| False positive rate | 0.0 % (0/3) |
| Time to detect, p50 / p90 (blocks) | 1 / 2 |
| Treasury value saved (mean) | 100.0 % |
| Passive treasury baseline (mean) | 71.1 % |
## Attack runs
| run_id | variant | seed | detected | first rule | ttd (blocks) | saved % | baseline % | warnings |
## Normal runs
| run_id | seed | false positive | alerts >= high |
## Misses, false positives, errors
- None.          (otherwise one line per case, with the reason)
## Method
(the 3 non-circularity rules below, and the step 1 definitions in one line each)
```

**6. `FakeApi` (in `backend/tests/test_t7_harness.py`).** Implements `EvalApi` in memory: `health()` returns a block that advances by 1 per call; `attack()` creates a `RunRecord` (`start_block = b`, `attack_start_block = b + 12`, `end_block = b + 80`, the 4 positions from 2.2) and writes it to `tmp_path/runs/`; `alerts()` returns a critical R1 at `attack_start_block + 1`; `decisions()` returns one decision with 4 `executed` `EMERGENCY_WITHDRAW` for the full amounts; `series()` sets `available_liquidity = "0"` on `lend-eth:WETH` (or `lend-eth:USDC` in the `usdc` variant); `run_normal()` creates a normal `RunRecord` with no alert ≥ high. Sleeps are injected (`sleep=lambda s: None`) so the test runs in under 1 s.

**7. `backend/api/metrics.py`.** Keep the existing route. Add: if `data/eval/metrics.json` exists but does not validate (broken JSON, wrong schema), log `WARNING data/eval/metrics.json invalid: <error>` and serve the fixture (never a 500). Read `settings.DATA_DIR` at call time (not at import) so tests can override it.

**8. `mk/t7.mk`.**
```make
RUNS ?= 10
EVAL_NORMAL ?= 3
EVAL_MINUTES ?= 2
eval: ## synthetic evaluation on local chain (backend must run with engine on)
	python -m evaluation.run_synthetic --runs $(RUNS) --normal $(EVAL_NORMAL) --minutes $(EVAL_MINUTES)
eval-report: ## rebuild data/eval/report.md from runs.jsonl
	python -m evaluation.report
test-t7:
	pytest -q backend/tests/test_t7_*.py
test-t7-e2e:
	T7_E2E=1 pytest -q backend/tests/test_t7_e2e.py
```
`EVAL_` prefix so as not to overwrite T2's `MINUTES` (all `mk/*.mk` are included in the same `Makefile`). Never redefine `NETWORK` in `mk/t7.mk` (it comes from `.env`, exported by the root `Makefile`, or from the command line). `make test-t7` includes `test_t7_e2e.py`, which skips itself while `T7_E2E` is not set; `make test` (which calls `test-t0` … `test-t9`) therefore never runs a real evaluation.

**Non-circularity rules (copy into `report.md`).**
1. Thresholds are frozen before the first run: their sha256 is written to `metrics.json` and `rules_frozen.json`, and anchored if possible; any alert carrying another `rules_version` aborts the evaluation.
2. The attack variants (`default`, `slow`, `usdc`) are written by T2 without looking at `rules.yaml`; T7 changes neither the rules nor the variants, and does not pick seeds after the fact (`base_seed` fixed beforehand).
3. Every miss, false positive and errored run is reported; no run is rerun or removed to improve a number.

#### Tests that must pass

Global command: `make test-t7` (= `pytest backend/tests/test_t7_*.py`, no network, < 10 s; T7-20 skipped without `T7_E2E=1`). Base test data: `REC` = `RunRecord(label="attack", variant="default", seed=1, start_block=100, end_block=180, attack_start_block=112, phase_blocks={"forged_mint":112,"liquidity_zero":138}, treasury_supplied_at_start={"lend-eth:WETH": 150e18, "lend-eth:USDC": 400000e6, "lend-avax:WETH": 100e18, "lend-avax:USDC": 300000e6})` (amounts as base-unit strings), `settle_blocks=10`.

| Id | Type | Command | Setup | Expected result |
|---|---|---|---|---|
| T7-01 | unit | `pytest backend/tests/test_t7_metrics.py::test_percentile_nearest_rank` | fixed lists | `[0,1,2,3,10]` → p50 = 2, p90 = 10; `[3]` → 3 and 3; `[2,0,1,1]` → p50 = 1, p90 = 2; `[]` → `ValueError` |
| T7-02 | unit | `…::test_detected_and_ttd` | `REC`; alerts: R1 critical block 113, R3 warning block 130, R2 critical block 105 (before the attack) | `detected is True`, `first_critical_block == 113`, `first_rule_id == "R1_BACKING_DROP"`, `ttd_blocks == 1`, `pre_attack_alerts == 1` |
| T7-03 | unit | `…::test_not_detected` | `REC`; alerts: R4 high block 140, R1 critical block 195 (outside window: 195 > 190) | `detected is False`, `ttd_blocks is None` |
| T7-04 | unit | `…::test_saved_full` | `REC`; 1 decision at block 114 with 4 `executed` `EMERGENCY_WITHDRAW`, full amounts | `start_value_usd == 1325000.0`, `saved_usd == 1325000.0`, `saved_pct == 100.0` |
| T7-05 | unit | `…::test_saved_ignores_non_executed` | `REC`; `lend-eth:WETH` 150 `executed`; `lend-eth:USDC` `failed`; `lend-avax:WETH` `pending_approval`; `lend-avax:USDC` `planned` with `amount` filled in | `saved_usd == 375000.0`, `saved_pct == 28.3` |
| T7-06 | unit | `…::test_saved_capped_and_unknown_key` | `REC`; `lend-eth:WETH` 200 WETH `executed`; one `lend-eth:rsETH` action `executed`; `lend-avax:WETH` 100 WETH `executed` with `tx_hash = "0xdry…"` | `saved_usd == 375000.0` (capped, dry-run excluded), 1 warning for the unknown key, 1 warning `"dry-run EMERGENCY_WITHDRAW excluded …"` |
| T7-07 | unit | `…::test_baseline` | `REC` | drained `{"lend-eth:WETH"}` → 71.7; `{"lend-eth:USDC"}` → 69.8; `set()` → 100.0 |
| T7-08 | unit | `…::test_drained_from_fixtures` | reads `fixtures/snapshots_attack.jsonl` and `snapshots_normal.jsonl`, converts each reserve into `SeriesPoint`; record `start_block=45201800`, `end_block=45201880` | attack → `{"lend-eth:WETH"}` (zero liquidity from 45,201,838); normal → `set()` |
| T7-09 | unit | `…::test_false_positive` | normal record `start_block=100`, `end_block=180` | `[R3 warning 120]` → `False`; `[R2 high 150]` → `True`; `[R2 high 195]` → `False`; consistent `max_severity` |
| T7-10 | unit | `…::test_aggregate` | 3 attacks (ttd 0, saved 100, baseline 71.7) / (ttd 2, saved 100, baseline 71.7) / (miss, saved 0, baseline 69.8); 2 normals including 1 FP | `runs_attack == 3`, `runs_normal == 2`, `detection_rate == 0.667`, `false_positive_rate == 0.5`, `ttd_blocks_p50 == 0`, `ttd_blocks_p90 == 2`, `saved_pct_mean == 66.7`, `baseline_saved_pct_mean == 71.1`; notes contain `"MISS "` and `"FALSE POSITIVE "`; `set(synthetic) == set(SYNTHETIC_KEYS)` |
| T7-11 | unit | `…::test_aggregate_no_detection` | 1 missed attack, 0 normal | `ttd_blocks_p50 == -1`, `ttd_blocks_p90 == -1`, `false_positive_rate == 0.0`, note `"no detected attack run: ttd undefined"` |
| T7-12 | unit | `…::test_rules_version` | temporary file containing `version: 1\n` | `"sha256:09bfcc6a14b83e2192b8673677725c84883ee9cd0c70e45c9ec09daa8f2b2847"`; format `^sha256:[0-9a-f]{64}$` |
| T7-13 | unit | `pytest backend/tests/test_t7_report.py::test_outputs_schema` | results from T7-10, `write_report` + writing `metrics.json` into `tmp_path` | `EvalMetrics.model_validate(json.load(...))` passes; `report.md` contains `"| Detection rate | 66.7 % (2/3) |"`, 3 lines in "Attack runs", 2 in "Normal runs", the miss line |
| T7-14 | API | `pytest backend/tests/test_t7_api.py::test_metrics_file_then_fixture` | `monkeypatch.setattr(settings, "DATA_DIR", tmp_path)`, `TestClient(app)` | without file: 200 and `synthetic.runs_attack == 0` (fixture); with the `metrics.json` from T7-13: 200 and `synthetic.detection_rate == 0.667` |
| T7-15 | API | `…::test_metrics_invalid_file` | `tmp_path/eval/metrics.json` = `"{oops"` | 200, body = fixture, one `WARNING` log |
| T7-16 | offline integration | `pytest backend/tests/test_t7_replay.py` | replays the 41 snapshots of each `.jsonl` through `backend.engine.Engine(Store()).process`; **`pytest.skip` if `backend.store` or `Engine` is still a stub (no alert on the attack series)** | attack: first critical alert `R1_BACKING_DROP` at block 45,201,812 → `ttd_blocks == 0` with `attack_start_block = 45201812`; normal: `false_positive is False` |
| T7-17 | offline harness | `pytest backend/tests/test_t7_harness.py::test_run_eval_with_fake_api` | `FakeApi` (step 6), `runs=3`, `normal=1`, `anchor=False`, `out_dir=tmp_path` | valid `metrics.json`; `runs_attack == 3`, `runs_normal == 1`, `detection_rate == 1.0`, `ttd_blocks_p50 == 1`, `saved_pct_mean == 100.0`, `baseline_saved_pct_mean == 71.1`; `runs.jsonl` has 4 lines; variants `default, slow, usdc` |
| T7-18 | offline harness | `…::test_rules_drift_aborts` | `FakeApi` where one alert has `rules_version="sha256:" + "0"*64` | `SystemExit` code 3 |
| T7-19 | offline harness | `…::test_failed_run_reported` | `FakeApi` where run 2 returns `status="failed"` | `runs_attack == 2`, note starting with `"ERRORED "`, line in `report.md` |
| T7-20 | end to end | `make test-t7-e2e` (= `T7_E2E=1 pytest backend/tests/test_t7_e2e.py`) | skip if `T7_E2E` is absent, if `127.0.0.1:8545` does not respond, or if `GET /api/health` is not `ok`/`local`/`engine_running`; backend started with `NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`; runs `python -m evaluation.run_synthetic --runs 2 --normal 1 --minutes 1` | exit code 0; `runs_attack == 2`, `runs_normal == 1`, `detection_rate == 1.0`, `false_positive_rate == 0.0`, `ttd_blocks_p90 <= 2` (aligned with E2E-1), `saved_pct_mean >= 99.0`, `baseline_saved_pct_mean < saved_pct_mean`, `rules_version` = sha256 of the current `rules.yaml` |

#### Definition of done

- [ ] `make test-t7` green without chain or backend (T7-01 to T7-19, T7-16 possibly skipped, T7-20 skipped without `T7_E2E=1`).
- [ ] `make test-t7-e2e` green on the local chain once T1 to T4 are merged.
- [ ] `make eval RUNS=10` produces a valid `data/eval/metrics.json`, `report.md`, `runs.jsonl`, `rules_frozen.json`.
- [ ] `GET /api/metrics` serves the measured file; never a 500 on a broken file.
- [ ] `metrics.json` contains exactly the 8 `synthetic` keys, units respected (rates 0..1, percentages 0..100).
- [ ] The notes list network, variants, anchoring, and every miss / false positive / error.
- [ ] "Method" section of `report.md` with the 3 non-circularity rules.
- [ ] `data/eval/metrics.json` and `data/eval/report.md` committed after the final measurement (T9 reads them from the repo).
- [ ] No file outside "Owned files" modified; any requests go in `docs/contract-requests.md`.

#### Known pitfalls

- **The reset redeploys**: an anchoring done before the first `reset` points to an old registry. Anchor after the first reset.
- **Denominator**: the `RunRecord` carries the 4 treasury positions, i.e. $1,325,000. Check `treasury_supplied_at_start` on the first real run (and that `fixtures/run_record.example.json` was indeed regenerated with the 4 positions): if any are missing, `saved_pct` is wrong.
- **`0xdry` hash**: in dry-run, withdrawals are marked `executed` with a `0xdry…` `tx_hash` without any funds moving. The harness runs with `DRY_RUN_ACTIONS=false`; if a `0xdry` shows up anyway, exclude it from the saved value and write it in the notes (step 4.3h), never count it.
- **Units**: `amount` in base units (string). Never convert to float before dividing by `10**decimals` on a Python `int`.
- **Stale old alert**: filter by block window, even though the reset empties the store.
- **`GET /api/alerts` is sorted newest to oldest**: sort by ascending `block_number` before looking for the first alert.
- **anvil `--block-time 1` and `POLL_INTERVAL_S=2`**: the engine may skip a block, a TTD of 0 to 2 is normal on local.
- **Make variable collision**: use `EVAL_NORMAL` / `EVAL_MINUTES`, not `MINUTES`.
- **`make normal` must be blocking**; otherwise the harness does not find a new `RunRecord`. Check with T2 as early as possible.
- **`make test` must never run a real evaluation** (it would reset a teammate's chain): the E2E is behind `T7_E2E=1`.
- **`data/` is ignored by git except `data/eval/metrics.json` and `data/eval/report.md`** (exception made by T0 in `.gitignore`): do not commit `runs.jsonl` or `rules_frozen.json` by mistake with `git add -f`.

#### Later (phase 2)

- **Mainnet replay of the real Aave incident of April 18, 2026** (block 24,908,285) via `ETH_ARCHIVE_RPC_URL`: an adapter `evaluation/replay_mainnet.py` reads the real Aave v3 Ethereum and rsETH block by block and produces `Snapshot(source="replay", network="replay")` fed to `Engine.process`; fills `mainnet_replay`: `exploit_block`, `first_alert_block`, `ttd_minutes`, `protocol_freeze_minutes`, `withdrawable_pct_at_alert`, `withdrawable_pct_at_freeze`, `alerts_on_normal_days`.
- **Alerts on real normal days**: 30 days of mainnet history, rate of alerts ≥ high per day.
- **Confidence intervals**: Wilson for `detection_rate` and `false_positive_rate`, bootstrap for the TTD percentiles.
- Lead over the protocol freeze (`phase_blocks.protocol_freeze − first_critical_block`), per-rule breakdown, evaluation on Fuji, gas cost of the response, additional adversarial variants (slow forged mint under the R1 threshold, multi-reserve drain).

#### Claude Code starter prompt

```
You are working on task T7 (Evaluation and metrics) from the TASKS.md file at the repo root.
1. Read TASKS.md sections 1 and 2 in full, then the T7 section in full. Read backend/models.py
   (Alert, Decision, Action, RunRecord, EvalMetrics, SeriesPoint, Health, DemoRun), backend/settings.py,
   backend/chain.py and backend/api/metrics.py.
2. Modify ONLY: evaluation/ (metrics.py, api_client.py, run_synthetic.py, report.py; not __init__.py, T0),
   backend/api/metrics.py, mk/t7.mk, backend/tests/test_t7_*.py. Nothing else: not rules.yaml, not the
   scenarios, not models.py, not fixtures/. If you need a change elsewhere or in the contract
   (section 2), do not edit: write the request in docs/contract-requests.md and tell me.
3. Start with tests T7-01 to T7-15 (backend/tests/test_t7_metrics.py, test_t7_report.py,
   test_t7_api.py) with the exact values from the T7 section, then write evaluation/metrics.py and
   report.py until they pass. Then FakeApi + T7-17 to T7-19, then run_synthetic.py.
   T7-16 and T7-20 skip themselves until T3/T2/T4 are delivered.
4. Work on mocks: hand-built RunRecord, Alert and Decision, FakeApi for the harness,
   fixtures/snapshots_*.jsonl for the series. fixtures/alerts.json and decisions.json are only
   format examples (R1 and DEC-fuji-45201812-1 at block 45201812). The reference denominator
   is $1,325,000 (4 positions). A 0xdry… tx_hash is never counted as saved.
5. Keep the metrics simple: exactly the 8 keys of EvalMetrics.synthetic. Everything else goes
   into notes or into "Later". Respect the non-circularity rules.
6. Before each commit: make test-t7 green (pytest backend/tests/test_t7_*.py), push often after each
   green test. Never run make eval against a teammate's chain.
```


---
### T8 · AWS, CI and demo hosting

**Goal.** Put the platform online on AWS (us-east-1) with a stable public URL that serves the dashboard and the API wired to Fuji, give T4/T5 the AWS resources (SNS topic, evidence bucket, Bedrock model) with a minimal IAM role, and keep `main` green with a CI (Python tests, Foundry tests, front build, secret scan). Nothing T8 does may leak a key: not in the repo, not in a Docker image, not in the front bundle.

**Depends on.**
- T0 → `requirements.txt`, `Makefile` (with `include mk/*.mk`), `.env.example`, `.gitignore`, `backend/` skeleton → available from the start. The `.gitignore` belongs to T0: it ignores `.env` and `.env.*` except `.env.example` (so `.env.fuji`, `.env.secrets`, `.env.canary`, `frontend/.env.local` are ignored); any other exception is requested in `docs/contract-requests.md`.
- T1 → `deployments/fuji.json` and `abi/*.json` **committed** → meanwhile: "skeleton" deployment with `USE_FIXTURES=true`, `ENGINE_ENABLED=false` (the API serves fixtures, no contract required).
- T3 → real `GET /api/health` route (real `rpc_ok`, `engine_running`, `block_number`) → meanwhile: `fixtures/health.json` (careful, it already says `network: fuji`, `rpc_ok: true`, see Known pitfalls).
- T6 → `frontend/package.json` with `build` scripts (and ideally `typecheck`), API calls on relative path `/api/...` → meanwhile: a minimal fake front `infra/testdata/frontend-stub/` (owned by T8) passed to the build via `FRONTEND_DIR`.
- T2 → `POST /api/demo/reset` which runs `make deploy` then `make seed` **inside the backend container** (on fuji, `make deploy` requires `FORCE=1` when a deployment already exists: T2 passes it) → so the backend image contains `make`, the `Makefile`, `mk/`, `contracts/` and Foundry (`WITH_FOUNDRY=true` by default); while waiting for T2: only check that `make -n deploy` and `make -n seed` resolve in the image.
- T4, T5 → read `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID` → nothing to wait for, T8 produces them.

**Unblocks.**
- T4: `SNS_TOPIC_ARN` (notifications) and `EVIDENCE_BUCKET` (evidence) + instance IAM permissions.
- T5: `BEDROCK_MODEL_ID` (Claude inference profile id) + `bedrock:InvokeModel` permission.
- T6: the public URL where the front is served and `/api` is proxied (same origin, no CORS in prod).
- T9: the demo URL for the jury, the README "Deploy" section, the fallback plan, the "no secret in the repo" evidence.
- Everyone: CI on every PR to `main`.

**Owned files.** (section 1.5: `infra/`, `.github/workflows/`, `mk/t8.mk`, `backend/tests/test_t8_*.py`)
- `infra/docker-compose.yml`, `infra/backend.Dockerfile`, `infra/backend.Dockerfile.dockerignore`, `infra/frontend.Dockerfile`, `infra/frontend.Dockerfile.dockerignore`, `infra/nginx.conf`
- `infra/deploy.sh`, `infra/render_env.sh`, `infra/user-data.sh`, `infra/scan_images.sh`, `infra/check_aws.py`
- `infra/fuji.env` (**non-secret** values forced on the instance), `infra/iam-policy.json`, `infra/gitleaks.toml`, `infra/setup-aws.md` (runbook)
- `infra/testdata/frontend-stub/` (fake front to test the build until T6 delivers)
- `.github/workflows/ci.yml`, `mk/t8.mk`
- `backend/tests/test_t8_infra.py`, `backend/tests/test_t8_check_aws.py`, `backend/tests/test_t8_deploy.py`

**Read before starting.** TASKS.md sections 1.3, 1.5, 1.6 (rules 5, 6, 8), 2.1 (variables), 2.9 (routes, port 8000), 2.10 (in-memory store: **a single process**), 2.11 (make); `backend/settings.py` (reads `.env` at the root, defaults), `backend/main.py` (engine start in the `startup` event), `fixtures/health.json`.

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Python dependencies | `requirements.txt` at the root | T0 | the skeleton's one |
| Backend code | `backend/`, `scenario/`, `evaluation/`, `fixtures/`, `abi/`, `deployments/` | T0..T5, T7 | T0 skeleton (serves fixtures) |
| Fuji addresses | `deployments/fuji.json` (2.3), committed | T1 | not needed in skeleton mode (`USE_FIXTURES=true`) |
| Buildable front | `frontend/package.json` + `package-lock.json`, `npm run build` → `frontend/dist/` | T6 | `infra/testdata/frontend-stub/` (build = node script that writes `dist/index.html` containing `<div id="root">`) |
| Foundry contracts | `contracts/foundry.toml`, `contracts/lib/` (submodules) | T1 | CI job `contracts` skipped if `contracts/foundry.toml` is missing |
| Real health | `Health` (2.9): `network`, `rpc_ok`, `engine_running`, `block_number` | T3 | `fixtures/health.json` |
| Fuji keys and RPC | variables 2.1 (`*_PK`, `BOT_PKS`, `RPC_URL`) | the team (generated for the event, testnet only) | local `.env` on `NETWORK=local` (public anvil keys) |
| AWS account | console + team temporary keys | organizers | none (`check_aws` tests in botocore stub mode) |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| Public URL | `http://<elastic-ip>/` (front) and `http://<elastic-ip>/api/*` (proxied API) | T6, T9, jury |
| `SNS_TOPIC_ARN` | `arn:aws:sns:us-east-1:<account_id>:secure-horizons-alerts` | T4 |
| `EVIDENCE_BUCKET` | `secure-horizons-evidence-<account_id>` (versioning, Object Lock if possible) | T4 |
| `BEDROCK_MODEL_ID` | inference profile id copied from `aws bedrock list-inference-profiles`, form `us.anthropic.claude-…` | T5 |
| Instance role | `secure-horizons-ec2-role` + profile `secure-horizons-ec2-profile`, policy `infra/iam-policy.json` | T4, T5 (boto3 without keys) |
| Images | `sh-backend`, `sh-frontend` built **on the instance** (no registry) | — |
| CI | `.github/workflows/ci.yml`, jobs `python`, `contracts`, `frontend`, `gitleaks`, `docker` | everyone |
| Make targets | `deploy-aws`, `aws-check`, `aws-smoke`, `aws-logs`, `aws-rollback`, `aws-allow-my-ip`, `docker-build`, `docker-up`, `docker-down`, `docker-smoke`, `scan-images`, `gitleaks`, `test-t8` (in `mk/t8.mk`) | everyone |
| Runbook | `infra/setup-aws.md` (step-by-step CLI commands + non-secret "Team values" table) | T9, team |

#### Detailed specification

**1. Backend image (`infra/backend.Dockerfile`, context = repo root).**
- Base `python:3.11-slim`. `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`. `WORKDIR /app`.
- `COPY requirements.txt .` then `pip install --no-cache-dir -r requirements.txt` (cached layer).
- `RUN apt-get update && apt-get install -y --no-install-recommends make git ca-certificates && rm -rf /var/lib/apt/lists/*`: `POST /api/demo/reset` (T2) calls `make deploy` and `make seed` from the container.
- `ARG WITH_FOUNDRY=true`; if `true`: `COPY --from=ghcr.io/foundry-rs/foundry:stable /usr/local/bin/forge /usr/local/bin/cast /usr/local/bin/` (fallback if the binaries don't run: `curl -L https://foundry.paradigm.xyz | bash && foundryup`), then `RUN cd contracts && forge build` after copying `contracts/` (the compilation cache is in the image, a `reset` on Fuji does not recompile). With `WITH_FOUNDRY=false`, `make deploy` is unavailable in the image: only for the case where T2 does not need it.
- **Explicit** copies only (never `COPY . .`): `Makefile`, `mk/`, `contracts/` (with `contracts/lib/`, OpenZeppelin submodules), `backend/`, `scenario/`, `evaluation/`, `fixtures/`, `abi/`, `deployments/`, `infra/check_aws.py` → `/app/infra/check_aws.py`. No `.env` in the image: the `Makefile`'s `-include .env` finds nothing and variables come from the container environment (`env_file`), which `make` inherits.
- `make deploy` writes `deployments/<network>.json` **and** `abi/`: both must be writable by the container user.
- Non-root user `app` with **uid 1000** (same uid as `ec2-user`, otherwise the `data/` volume is not writable). `mkdir -p /app/data && chown -R 1000:1000 /app/data /app/deployments /app/abi /app/contracts` (the `reset` writes deployments, ABIs, `contracts/out` and `contracts/broadcast`, and T2 creates `data/runtime/<network>/maintenance.flag`).
- `EXPOSE 8000`. `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]`: **no** `--reload`, **no** `--workers` (the store and the engine live in memory in a single process, 2.10).
- `infra/backend.Dockerfile.dockerignore` (exclusion file specific to this Dockerfile, read by BuildKit): `.git`, `.env`, `.env.*`, `**/.env`, `**/.env.*`, `data/`, `frontend/`, `**/node_modules`, `**/__pycache__`, `contracts/out`, `contracts/cache`, `*.pem`, `*.key`.

**2. Frontend image (`infra/frontend.Dockerfile`, multi-stage).**
- `ARG FRONTEND_DIR=frontend`. `build` stage: `node:20-alpine`, `WORKDIR /src/frontend`, `COPY ${FRONTEND_DIR}/package.json ${FRONTEND_DIR}/package-lock.json* ./`, `npm ci` (or `npm install` if no lock, stub only), `COPY ${FRONTEND_DIR}/ ./`, `COPY fixtures/ /src/fixtures/` (if T6 imports `../fixtures`), `ENV VITE_API_URL=` (empty: the front calls `/api/...` on a relative path, same origin via nginx, 2.1) and `ENV VITE_USE_FIXTURES=false`, then `npm run build` → `/src/frontend/dist`.
- Final stage: `nginx:1.27-alpine`, `COPY infra/nginx.conf /etc/nginx/conf.d/default.conf`, `COPY --from=build /src/frontend/dist /usr/share/nginx/html`. No secret environment variable, no secret `ARG`.
- `infra/frontend.Dockerfile.dockerignore`: same as the backend + `frontend/.env*` (Vite injects every `VITE_*` from the front's `.env*` files **into the public bundle**), `frontend/dist`, `frontend/node_modules`.

**3. `infra/nginx.conf`.**
```nginx
limit_req_zone $binary_remote_addr zone=demo:1m rate=6r/m;
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  gzip on; gzip_types application/json application/javascript text/css;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  location /api/demo/ { limit_req zone=demo burst=2 nodelay; proxy_pass http://backend:8000; proxy_read_timeout 300s; }
  location /api/      { proxy_pass http://backend:8000; proxy_read_timeout 120s; }
  location /assets/   { expires 7d; add_header Cache-Control "public, immutable"; }
  location /          { try_files $uri $uri/ /index.html; add_header Cache-Control "no-cache"; }
}
```
- `proxy_pass http://backend:8000;` **without** a trailing slash: the `/api` prefix is kept (FastAPI routes are mounted under `/api`, 2.9). The `proxy_set_header` at `server` level are inherited by both `location` blocks.
- `/api/demo/reset` on Fuji redeploys the contracts: the response can take more than a minute, hence `proxy_read_timeout 300s`.
- The limit on `/api/demo/` (6 req/min/IP) stops a visitor from rerunning the attack in a loop and draining the Fuji gas. Nothing else in the MVP.

**4. `infra/docker-compose.yml`.**
- Project named `sh` (`-p sh`). Service `backend`: `build: {context: .., dockerfile: infra/backend.Dockerfile, args: {WITH_FOUNDRY: "${WITH_FOUNDRY:-true}"}}`, `image: sh-backend`, `env_file: [{path: "${ENV_FILE:-../.env}", required: false}]`, `volumes: ["${DATA_PATH:-../data}:/app/data", "../deployments:/app/deployments"]`, `ports: ["127.0.0.1:8000:8000"]` (never publicly exposed), `healthcheck: python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"` every 10 s, `restart: unless-stopped`, `logging: {driver: json-file, options: {max-size: 10m, max-file: "3"}}`.
- Service `frontend`: `build: {context: .., dockerfile: infra/frontend.Dockerfile, args: {FRONTEND_DIR: "${FRONTEND_DIR:-frontend}"}}`, `image: sh-frontend`, `ports: ["${FRONT_PORT:-80}:80"]`, `depends_on: {backend: {condition: service_healthy}}`, `restart: unless-stopped`.
- No `*_PK` variable or RPC URL written in the file: everything comes from `ENV_FILE`.

**5. Instance configuration: `infra/fuji.env` + secrets.**
- `infra/fuji.env` (committed, **no secret**): `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`, `POLL_INTERVAL_S=2`, `AWS_REGION=us-east-1`, `EXPLORER_URL=https://testnet.snowtrace.io`, `RPC_FALLBACK_URL=https://api.avax-test.network/ext/bc/C/rpc`.
- Secrets and resource identifiers (`RPC_URL` with provider key, `DEPLOYER_PK`, `OWNER_PK`, `GUARDIAN_PK`, `PROTOCOL_GUARDIAN_PK`, `ATTACKER_PK`, `EVIDENCE_PK`, `BOT_PKS`, `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID`, `ALERT_WEBHOOK_URL`): two possible sources, chosen by `ENV_SOURCE`:
  - `ssm` (recommended): one `SecureString` parameter per variable under `/secure-horizons/fuji/<VAR>`; `infra/render_env.sh` run **on the instance** does `aws ssm get-parameters-by-path --path /secure-horizons/fuji/ --with-decryption --recursive --query 'Parameters[].[Name,Value]' --output text` and writes `NAME=value`.
  - `file`: a local `.env.fuji` (ignored by git via the `.env.*` rule in T0's `.gitignore`) copied with `scp`.
- Final file on the instance: `~/sh/shared/.env`, `chmod 600`, = secrets **then** `infra/fuji.env` appended at the end (the last occurrence wins: the 4 forced values cannot be overwritten by mistake).
- Never a secret in `user-data`, in a Docker `ARG`/`ENV`, in `fuji.env` or in a `VITE_*` variable.

**6. AWS setup (`infra/setup-aws.md`, one person, CLI `--region us-east-1`).** Naming prefix `secure-horizons-`. The runbook contains the exact commands, in this order:
1. `aws sts get-caller-identity` → note `ACCOUNT_ID`.
2. SNS: `aws sns create-topic --name secure-horizons-alerts`; one `aws sns subscribe --protocol email --notification-endpoint <email>` per member; each one **confirms** the email (check spam).
3. S3: `aws s3api create-bucket --bucket secure-horizons-evidence-$ACCOUNT_ID --object-lock-enabled-for-bucket` (no `--create-bucket-configuration` in us-east-1; Object Lock turns on versioning); if the option fails: create without it, then `put-bucket-versioning Status=Enabled`. `put-public-access-block` with all 4 booleans `true`. **No** default retention in `COMPLIANCE` mode (at most `GOVERNANCE` 1 day), otherwise the account can no longer be cleaned up.
4. Bedrock: a single person fills in the Anthropic "first-time use" form in the Bedrock console (Model catalog) and makes the **first** invocation from the console; then `aws bedrock list-inference-profiles --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId"`; pick a `us.anthropic.claude-…` Haiku profile (fast, cheap, suggested for T5) or Sonnet; copy the **exact** listed id into `BEDROCK_MODEL_ID`. Never build the id by hand.
5. IAM: role `secure-horizons-ec2-role` (trust `ec2.amazonaws.com`), inline policy `infra/iam-policy.json` (after replacing `<ACCOUNT_ID>`), profile `secure-horizons-ec2-profile`. Exact actions and resources:
   - `sns:Publish` on the topic ARN;
   - `s3:PutObject`, `s3:GetObject` on `arn:aws:s3:::secure-horizons-evidence-<ACCOUNT_ID>/*`; `s3:DeleteObject` **only** on `…/healthcheck/*` (for `check_aws.py`);
   - `bedrock:InvokeModel` on `arn:aws:bedrock:us-east-1:<ACCOUNT_ID>:inference-profile/us.anthropic.*` **and** `arn:aws:bedrock:*::foundation-model/anthropic.*` (a `us.` profile routes to several regions);
   - `ssm:GetParametersByPath`, `ssm:GetParameter` on `arn:aws:ssm:us-east-1:<ACCOUNT_ID>:parameter/secure-horizons/fuji*` (add `kms:Decrypt` only if a KMS `AccessDenied` shows up).
   - No `*` action, no `*` resource except the model ARNs above.
6. Network: SSH key `secure-horizons-key` (the `.pem` stays on the workstation, `chmod 400`, never in the repo); group `secure-horizons-demo-sg`: ingress `80/tcp` from `0.0.0.0/0`, `22/tcp` from the team's `/32` IPs only; **no** 8000.
7. EC2: `aws ec2 run-instances --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --instance-type t3.medium --key-name secure-horizons-key --security-group-ids <sg> --iam-instance-profile Name=secure-horizons-ec2-profile --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2 --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' --user-data file://infra/user-data.sh --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=secure-horizons-demo}]'`; then allocate and associate an Elastic IP (stable URL after a stop/start).
8. SSM: `aws ssm put-parameter --type SecureString --name /secure-horizons/fuji/GUARDIAN_PK --value "$GUARDIAN_PK"` for each secret (from shell variables, never typed in clear into a committed file; `history -c` afterwards).
9. "Team values" table at the end of the runbook: public IP, topic ARN, bucket name, `BEDROCK_MODEL_ID` (non-secret values).
- `infra/user-data.sh`: `dnf install -y docker git`; `systemctl enable --now docker`; `usermod -aG docker ec2-user`; installs the `docker-compose` and `docker-buildx` plugins (GitHub binaries, x86_64) into `/usr/local/lib/docker/cli-plugins/`; `mkdir -p /home/ec2-user/sh/{releases,shared/data}` and `chown -R ec2-user`.

**7. `infra/deploy.sh` (run from a team workstation).**
- Usage: `infra/deploy.sh --host <ip> --key <pem> [--env-source file|ssm] [--env-file .env.fuji] [--dry-run] [--rollback]`. `set -euo pipefail`. Exit codes: `0` OK, `2` usage, `3` pre-check failed, `4` transfer/SSH failed, `5` health KO after deployment.
- Pre-checks (`3` on failure): we are in a git repo; `deployments/fuji.json` and `abi/` are **tracked** by git (otherwise message "commit deployments/fuji.json first") unless `--allow-skeleton`; in `file` mode, the file exists, is `600`, and contains non-empty `GUARDIAN_PK`, `EVIDENCE_PK`, `RPC_URL` (message `missing GUARDIAN_PK`); warning if the working tree is not clean (only committed code ships).
- Release: `REL=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)`; upload = `git ls-files -z --recurse-submodules | tar --null -T - -czf - | ssh ... "mkdir -p ~/sh/releases/$REL && tar -xzf - -C ~/sh/releases/$REL"` (ships only tracked files, so never `.env`; includes the OpenZeppelin submodules, unlike `git archive`).
- Secrets: `file` → `scp` to `~/sh/shared/.env.secrets` then `chmod 600`; `ssm` → `bash ~/sh/releases/$REL/infra/render_env.sh > ~/sh/shared/.env.secrets`. Then `cat .env.secrets infra/fuji.env > ~/sh/shared/.env && chmod 600`.
- Launch: `ln -sfn ~/sh/releases/$REL ~/sh/current && cd ~/sh/current && ENV_FILE=/home/ec2-user/sh/shared/.env DATA_PATH=/home/ec2-user/sh/shared/data docker compose -p sh -f infra/docker-compose.yml up -d --build --remove-orphans`.
- Wait: up to 40 attempts 3 s apart on `http://<host>/api/health`; success if `network == "fuji"` and `rpc_ok == true`; otherwise prints `docker compose logs --tail 80 backend` and exits with `5`.
- Cleanup: keeps the last 3 releases. `--rollback`: repoints `current` to the previous release and reruns `up -d`.
- `--dry-run`: opens no connection, prints `DRY-RUN` then each planned command and the list of files that would be shipped.
- Logs: one line per step, e.g. `[deploy] release=20261011T081502Z-3fa91c2 files=412 env=ssm`, `[deploy] health ok block=45213377 rpc_ok=true`, `[deploy] DONE http://203.0.113.10/`. Never print `.env` contents.

**8. `infra/check_aws.py` (stdlib + boto3, run in the backend container or on a workstation).**
```python
@dataclass
class CheckResult:
    name: str          # "sts" | "sns" | "s3" | "bedrock" | "http"
    status: str        # "OK" | "FAIL" | "SKIP"
    detail: str
    duration_ms: int

def check_sts(sts) -> CheckResult                                   # get_caller_identity → account + role arn
def check_sns(sns, topic_arn: str) -> CheckResult                   # publish Subject="secure-horizons check_aws", Message="check_aws test <iso>"
def check_s3(s3, bucket: str, prefix: str = "healthcheck/") -> CheckResult   # put → get (identical content) → delete
def check_bedrock(brt, model_id: str) -> CheckResult                # converse, 1 message "Reply with the single word OK.", maxTokens=64
def check_http(base_url: str, wait_s: float = 6.0) -> CheckResult   # /api/health x2, /api/state, /
def run_checks(only: set[str], session, base_url: str | None) -> list[CheckResult]
def format_line(r: CheckResult) -> str                              # f"{status:<5} {name:<8} {detail} ({ms} ms)"
def main(argv: list[str] | None = None) -> int
```
- Variables come from `backend.settings` if importable (`AWS_REGION`, `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID`), otherwise from `os.environ`. Empty variable → `SKIP` with the reason (`SNS_TOPIC_ARN empty`), never `FAIL`.
- Each check catches `botocore.exceptions.ClientError`, `BotoCoreError`, `urllib.error.URLError` and returns `FAIL` with `code: message`; no exception propagates; no secret variable value is printed.
- S3: key `healthcheck/check-<yyyymmddTHHMMSSZ>-<4 hex>.txt`, body `b"secure-horizons check_aws <iso>"`; `FAIL "content mismatch"` if the `get` differs.
- Bedrock: no `temperature`/`topP` (rejected with a 400 by recent Claude models); a single request per run; `OK` if the reply text is non-empty; detail `model=<id> reply="OK" in=<n> out=<n> tokens`.
- HTTP (`--public-url http://<ip>`): `OK` only if `network=="fuji"`, `chain_id==43113`, `rpc_ok`, `engine_running`, `block_number` of the 2nd call (6 s later) **strictly greater** than the 1st, `GET /api/state` → `network=="fuji"` (a `503` `{"detail": "no snapshot yet"}` means the engine has not read any block yet: `FAIL "no snapshot yet"`, retry a few seconds later), `GET /` → 200 and contains `<div id="root">`.
- CLI: `--only sts,sns,s3,bedrock,http` (default: `sts,sns,s3,bedrock`, plus `http` if `--public-url`), `--strict` (a `SKIP` counts as a failure). Last line: `SUMMARY <n> OK, <n> FAIL, <n> SKIP`. Exit code: `0` if no `FAIL` (and no `SKIP` in `--strict`), `1` if at least one `FAIL`, `2` if only `SKIP` in `--strict`.

**9. `infra/scan_images.sh`.** For `sh-backend` and `sh-frontend`: (a) `docker history --no-trunc --format '{{.CreatedBy}}'` contains no `_PK`, no `SECRET`, no `RPC_URL=`; (b) `docker image inspect -f '{{json .Config.Env}}'` contains no `_PK`; (c) `docker run --rm --entrypoint sh <img> -c "find / -xdev \( -name '.env' -o -name '.env.*' \) 2>/dev/null"` is empty; (d) filesystem export (`docker create` + `docker export` → `/app` or `/usr/share/nginx/html` extracted to a temp folder) then `gitleaks detect --no-git --source <dir> --config infra/gitleaks.toml` → no leak. `--canary` mode: writes a fake secret `T8_CANARY=sh-canary-7f3a9c41` into `.env.canary` (root) and `VITE_T8_CANARY=sh-canary-7f3a9c41` into `frontend/.env.local` **only if they don't exist**, rebuilds, checks with `grep -r sh-canary-7f3a9c41` that it appears in no image, then deletes both files (`trap` to clean up even on error). Exits `1` on the first problem, with the check name.

**10. CI (`.github/workflows/ci.yml`).** Triggers: `push` on `main`, `pull_request`. `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`. Jobs (all `ubuntu-latest`):
- `python`: `actions/checkout@v4` with `submodules: recursive`; `actions/setup-python@v5` 3.11 with pip cache; `foundry-rs/foundry-toolchain@v1` (for `anvil` and `forge`); `pip install -r requirements.txt`; if `contracts/foundry.toml` exists: `anvil --block-time 1 &`, wait for the RPC (`cast block-number` in a loop, 30 s max), then `make deploy NETWORK=local` and `make seed NETWORK=local`; then `python -m pytest backend/tests -q` with `env: {NETWORK: local, USE_FIXTURES: "true", ENGINE_ENABLED: "false", DRY_RUN_ACTIONS: "true"}`. No secret (on `local`, `settings.private_key` falls back to the anvil accounts), no AWS access.
- `contracts`: checkout with `submodules: recursive`; steps gated by `if: hashFiles('contracts/foundry.toml') != ''`; `forge build --sizes` then `forge test -vvv` in `contracts/`.
- `frontend`: `actions/setup-node@v4` node 20, npm cache (`cache-dependency-path: frontend/package-lock.json`); gated by `hashFiles('frontend/package.json') != ''`; `npm ci`; `npm run typecheck --if-present` then, if missing, `npx tsc --noEmit`; `npx vitest run`; `npm run build`.
- `gitleaks`: checkout `fetch-depth: 0`; downloads the gitleaks v8 binary (pinned version) from GitHub releases; `gitleaks detect --source . --config infra/gitleaks.toml --redact -v --exit-code 1`. No `gitleaks-action` (license required for organization accounts).
- `docker`: `docker compose -f infra/docker-compose.yml build` (with `FRONTEND_DIR=infra/testdata/frontend-stub` if `frontend/package.json` is missing) then `bash infra/scan_images.sh`.
- `infra/gitleaks.toml`: `[extend] useDefault = true`; allowlist limited to `fixtures/.*\.json(l)?$` (sha256 hashes and test addresses) and to the public anvil mnemonic in `backend/settings.py`. Never an allowlist on `.env*`.

**11. `mk/t8.mk`.** Variables: `HOST`, `SSH_KEY ?= ~/.ssh/secure-horizons-key.pem`, `ENV_SOURCE ?= ssm`, `ENV_FILE ?= .env.fuji`. **Never** redefine `NETWORK` (it comes from `.env` or the command line, 2.11). Targets:
- `test-t8` (called by `make test`): `python -m pytest backend/tests/test_t8_*.py -q` + the infra checks that need neither AWS nor network: `bash -n infra/*.sh` + `shellcheck infra/*.sh` (if installed) + `docker compose -f infra/docker-compose.yml config -q` (if docker is present).
- `docker-build`, `docker-up` (`up -d --build`, `ENV_FILE` defaults to `../.env`), `docker-down`, `docker-smoke` (test T8-07), `scan-images`, `gitleaks`.
- `deploy-aws`: `bash infra/deploy.sh --host $(HOST) --key $(SSH_KEY) --env-source $(ENV_SOURCE) --env-file $(ENV_FILE)` (clear error if `HOST` is empty).
- `aws-check`: `ssh ... "cd ~/sh/current && docker compose -p sh -f infra/docker-compose.yml exec -T backend python infra/check_aws.py"` then `python3 infra/check_aws.py --only http --public-url http://$(HOST)` locally.
- `aws-smoke`: only the `http` check. `aws-logs`: `docker compose logs -f --tail 200`. `aws-rollback`: `deploy.sh --rollback`. `aws-allow-my-ip`: adds `$(curl -s https://checkip.amazonaws.com)/32` on port 22 of the security group.

**12. Fallback plan (rehearse once, before the demo).** (a) Same compose on a laptop pointed at Fuji: `make docker-up ENV_FILE=../.env.fuji` → `http://localhost/`; (b) `make demo` on local anvil (backend started with `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false`); (c) recorded video (T9). The switchover order is written at the top of `infra/setup-aws.md`.

#### Tests that must pass

Global command: `make test-t8` (T8-01 to T8-06). The others are integration tests run by hand, with their make target.

- **T8-01 · unit** · `pytest backend/tests/test_t8_infra.py -q`. `test_compose_services`: `yaml.safe_load(infra/docker-compose.yml)["services"]` has exactly the keys `{"backend", "frontend"}`; `backend.build.dockerfile == "infra/backend.Dockerfile"` and `context == ".."`; every published backend port starts with `127.0.0.1:`. `test_backend_command_single_process`: the command (Dockerfile CMD or compose `command`) contains `uvicorn backend.main:app`, `--host 0.0.0.0`, `--port 8000`, and contains neither `--reload` nor `--workers`. `test_no_secret_in_compose`: no key ending in `_PK` in `environment`, no `0x` + 64 hex string in the file.
- **T8-02 · unit** · same file. `test_dockerfiles_never_copy_env`: no `COPY`/`ADD` line of either Dockerfile contains `.env`, no `COPY . .` line, no `ARG`/`ENV` containing `_PK`. `test_backend_image_can_reset`: `infra/backend.Dockerfile` contains an `apt-get install` line that installs `make`, and `COPY` of `Makefile`, `mk/` and `contracts/`. `test_frontend_api_url_empty`: `infra/frontend.Dockerfile` sets `VITE_API_URL` to an empty value before `npm run build`. `test_dockerignore_excludes_env`: both `*.dockerignore` contain `.env`, `**/.env*` (or `**/.env.*`) and `data/`; the front one contains `frontend/.env*`.
- **T8-03 · unit** · `test_nginx_conf`: `infra/nginx.conf` contains `listen 80`, `location /api/`, `proxy_pass http://backend:8000;` (exactly, no trailing `/`), `try_files $uri $uri/ /index.html;`, `limit_req` on `/api/demo/`. `test_fuji_env_forced_values`: parsed `infra/fuji.env` contains `NETWORK=fuji`, `CHAIN_ID=43113`, `ENGINE_ENABLED=true`, `USE_FIXTURES=false`, `DRY_RUN_ACTIONS=false`, `AWS_REGION=us-east-1`, and no `*_PK`, `RPC_URL`, `SNS_TOPIC_ARN` key. `test_iam_policy_minimal`: the set of actions in `infra/iam-policy.json` is exactly `{sns:Publish, s3:PutObject, s3:GetObject, s3:DeleteObject, bedrock:InvokeModel, ssm:GetParametersByPath, ssm:GetParameter}`; no `*` action; the `s3:DeleteObject` resource ends with `/healthcheck/*`.
- **T8-04 · unit** · `test_ci_workflow_jobs`: `ci.yml` loaded (careful, PyYAML reads the `on` key as `True`: `wf.get("on", wf.get(True))`); jobs ⊇ `{"python", "contracts", "frontend", "gitleaks"}`; triggers `push` (branches contains `main`) and `pull_request`; the string `3.11` and the string `20` appear in the `python` and `frontend` jobs; the `gitleaks` job does not use `gitleaks/gitleaks-action`; the `python` job checks out with `submodules: recursive` and contains `make deploy` then `make seed` before `pytest`.
- **T8-05 · unit (no network)** · `pytest backend/tests/test_t8_check_aws.py -q`. The module is loaded with `importlib.util.spec_from_file_location("check_aws", "infra/check_aws.py")`. Clients `boto3.client(<svc>, region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")` + `botocore.stub.Stubber`:
  - `test_check_sns_ok`: `publish` expected with `TopicArn="arn:aws:sns:us-east-1:123456789012:secure-horizons-alerts"`, `Subject="secure-horizons check_aws"`, `Message=ANY`, response `{"MessageId": "m-1"}` → `status == "OK"`, `"MessageId=m-1" in detail`.
  - `test_check_sns_denied`: `add_client_error("publish", service_error_code="AuthorizationError", http_status_code=403)` → `FAIL`, `"AuthorizationError" in detail`.
  - `test_check_s3_roundtrip_ok`: `put_object` → `{}`; `get_object` → `Body=StreamingBody(io.BytesIO(body), len(body))` with the body sent (obtained via a `monkeypatch` of the body generator, or `expected_params` with `ANY`); `delete_object` → `{}` → `OK`.
  - `test_check_s3_content_mismatch`: `get_object` returns `b"other"` → `FAIL`, `"content mismatch" in detail`.
  - `test_check_bedrock_ok`: `converse` → `{"output": {"message": {"role": "assistant", "content": [{"text": "OK"}]}}, "stopReason": "end_turn", "usage": {"inputTokens": 14, "outputTokens": 2, "totalTokens": 16}, "metrics": {"latencyMs": 420}}` → `OK`, `'reply="OK"' in detail`, `"in=14 out=2" in detail`; and the parameters sent do not contain `temperature`.
  - `test_missing_config_is_skip`: `check_sns(None, "")` → `SKIP`, `"SNS_TOPIC_ARN empty" in detail`; same for `check_s3(None, "")`, `check_bedrock(None, "")`.
  - `test_main_exit_codes`: `monkeypatch` of `run_checks` → `[OK, OK]` gives `0`; `[OK, FAIL]` gives `1`; `[SKIP]` with `--strict` gives `2`; stdout ends with `SUMMARY 1 OK, 1 FAIL, 0 SKIP` in the 2nd case.
  - `test_format_line`: `format_line(CheckResult("sns", "OK", "MessageId=m-1", 140)) == "OK    sns      MessageId=m-1 (140 ms)"`.
- **T8-06 · unit** · `pytest backend/tests/test_t8_deploy.py -q`. `test_scripts_syntax`: `bash -n` on `deploy.sh`, `render_env.sh`, `user-data.sh`, `scan_images.sh` → code `0`. `test_deploy_missing_secret_refused`: temp file `600` containing only `RPC_URL=https://example.invalid`; `bash infra/deploy.sh --dry-run --host 203.0.113.10 --key /dev/null --env-source file --env-file <tmp>` → code `3`, output contains `missing GUARDIAN_PK`. `test_deploy_dry_run_ships_no_env` (skipped if no git repo): with a complete env file of **fake** values (`GUARDIAN_PK=0x` + `11`×32, etc.) and `--allow-skeleton` → code `0`, output contains `DRY-RUN` and `docker compose -p sh -f infra/docker-compose.yml up -d --build`, and no line of the file list is `.env` or ends with `/.env`.
- **T8-07 · local integration (docker)** · `make docker-smoke`. Setup: local `.env` = `.env.example` (`NETWORK=local`, `USE_FIXTURES=true`); if T6 has not delivered, `FRONTEND_DIR=infra/testdata/frontend-stub`. Commands and expected results: `docker compose -f infra/docker-compose.yml build` → code 0; `up -d` then wait for `healthy` (≤ 60 s); `curl -fsS localhost:8000/api/health` → JSON with the 7 `Health` fields; `curl -fsS localhost/api/health` → the **same** JSON (the proxy works); `curl -fsS localhost/` → 200, contains `<div id="root">`; `curl -s -o /dev/null -w '%{http_code}' localhost/incidents/INC-20261011-001` → `200` (SPA fallback); `curl -s localhost/api/does-not-exist` → `404` with `{"detail":"Not Found"}` (from FastAPI, not nginx); `curl -s -o /dev/null -w '%{http_code}' localhost:8000` from another machine → refused (port bound to 127.0.0.1). `docker compose down` at the end.
- **T8-08 · image security** · `make scan-images` then `bash infra/scan_images.sh --canary`. Expected: `OK history`, `OK env`, `OK no-dotenv`, `OK gitleaks` for each image; the canary `sh-canary-7f3a9c41` is found neither in `/app` nor in `/usr/share/nginx/html`; the canary files are deleted after the test (clean `git status`).
- **T8-09 · repo secrets** · `make gitleaks` (= `gitleaks detect --source . --config infra/gitleaks.toml --redact -v`) → `no leaks found`, code 0, on the whole history. Negative check (fake data only): on a throwaway branch, commit a file containing a fake AWS key in the official test-set format (`AKIA` + 16 characters) → gitleaks code 1; delete the branch.
- **T8-10 · CI** · open a test PR: the 5 jobs go green; after merge, the last run on `main` is green (`gh run list --branch main --limit 1` → `completed success`).
- **T8-11 · AWS, resources** · `make aws-check HOST=<ip>`. Expected in the container, 4 lines then the summary, code 0:
  `OK    sts      account=<id> arn=arn:aws:sts::<id>:assumed-role/secure-horizons-ec2-role/i-… (…)` · `OK    sns      MessageId=… (…)` · `OK    s3       put/get/delete s3://secure-horizons-evidence-<id>/healthcheck/check-….txt (…)` · `OK    bedrock  model=us.anthropic.claude-… reply="OK" in=… out=… tokens (…)` · `SUMMARY 4 OK, 0 FAIL, 0 SKIP`. Each subscribed member receives the "secure-horizons check_aws" email. The `sts` check proves the container gets the role credentials (IMDS hop limit = 2).
- **T8-12 · AWS, public URL** · `make aws-smoke HOST=<ip>` (after T1 and T3 deliver) → `OK    http     network=fuji chain_id=43113 rpc_ok=true engine_running=true block <n1> -> <n2> (n2 > n1)`; from a phone on 4G, `http://<ip>/` shows the dashboard. Before T1/T3 (skeleton deployment): only `GET /` and `GET /api/health` returning 200 are required.
- **T8-13 · resilience and network** · `ssh … sudo reboot` → at most 3 min later, `make aws-smoke` is `OK` again with no intervention (`restart: unless-stopped`, docker enabled). `aws ec2 describe-security-groups --group-names secure-horizons-demo-sg --query 'SecurityGroups[0].IpPermissions'`: port 22 has no `0.0.0.0/0` range, port 8000 does not appear. `make aws-rollback` goes back to the previous release and `aws-smoke` stays `OK`.
- **T8-14 · fallback plan** · on a laptop: `make docker-up ENV_FILE=../.env.fuji` → `http://localhost/api/health` returns `network: fuji`; `make demo` starts locally. Write the observed switchover time in `infra/setup-aws.md`.

#### Definition of done

- [ ] `make test-t8` green (T8-01 to T8-06), locally and in the CI `python` job.
- [ ] `make docker-smoke` green with the real front (no more stub); `make scan-images` and `--canary` green.
- [ ] CI: 5 green jobs on `main`; `gitleaks` green on the whole history.
- [ ] SNS topic created, emails confirmed by every member; bucket versioned (Object Lock if accepted), public access blocked; Bedrock profile chosen and invoked once.
- [ ] `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID` handed to T4/T5 and written in the "Team values" table of `infra/setup-aws.md`.
- [ ] Secrets only in SSM (or `.env.fuji` outside the repo); no secret in the repo, the images, `user-data` or the bundle.
- [ ] `make deploy-aws` works end to end from at least two different workstations.
- [ ] `make aws-check` → `SUMMARY 4 OK`; `make aws-smoke` → `OK` with `engine_running=true` and an advancing block.
- [ ] Reboot and rollback tested (T8-13); fallback plan rehearsed (T8-14).
- [ ] `infra/setup-aws.md` lets someone else recreate everything without help.

#### Known pitfalls

- **Misleading fixture**: until T3 wires `/api/health`, the fixture already answers `network: fuji`, `rpc_ok: true`. Only `engine_running == true` and an increasing `block_number` prove we really read Fuji.
- **IMDSv2 and containers**: with a hop limit of 1, boto3 in a container finds no credentials (`NoCredentialsError`). Set `HttpPutResponseHopLimit=2` (`aws ec2 modify-instance-metadata-options` if the instance already exists).
- **A single uvicorn worker**: with `--workers 2`, two engines run, two stores diverge, and the same alert triggers two withdrawals.
- **`proxy_pass` with a trailing `/`**: `proxy_pass http://backend:8000/;` strips `/api` and every route returns 404.
- **Vite and variables**: any `VITE_*` read at build time ends up in clear in the public JS. No key may ever be named `VITE_…`.
- **`git archive` ignores submodules** (OpenZeppelin) and uncommitted files: we ship `git ls-files --recurse-submodules`, and `deployments/fuji.json` must be committed before `deploy-aws`.
- **No manual fix on the instance**: anything not pushed is lost. Push often after each green test, the AWS account is wiped at the end of the event.
- **Object Lock in COMPLIANCE mode**: objects cannot be deleted before expiry, even as root. GOVERNANCE or no default retention.
- **Bedrock**: first-time use form required (one person only); model id must be copied from the list; a `us.` profile requires permissions on the `foundation-model` ARNs of several regions; no `temperature` on recent models; under 1 request/s per person; no jailbreak testing.
- **SNS**: an unconfirmed email subscription receives nothing even though `publish` succeeds; `Subject` limited to 100 ASCII characters, no line breaks.
- **Team IP changes** (venue Wi-Fi): SSH blocked. `make aws-allow-my-ip`, never `0.0.0.0/0` on 22.
- **Public Fuji RPC**: rate limited, the 2 s monitoring loop saturates it. Use a provider RPC in `RPC_URL` (secret) and the public one in `RPC_FALLBACK_URL`.
- **`data/` volume permissions**: the container uid must be 1000 (ec2-user), otherwise `PermissionError` when writing `data/runtime/fuji/`.
- **Amazon Linux 2023**: `docker compose` (plugin) is not installed by default, nor `buildx`; `user-data.sh` installs them. The default 8 GB disk fills up with Docker layers: 30 GB.
- **Images built on the instance** (x86_64): do not push an image built on an ARM Mac.
- **GitHub Actions**: `hashFiles()` cannot be used in a job-level `if` before checkout; put it at step level. `gitleaks-action` v2 requires a license for an organization repo: use the binary.
- **PyYAML and the `on` key** of the workflow read as boolean `True` (T8-04).
- **Organizer rules**: we only test what we deployed, synthetic data, no load testing on the public URL or on AWS services, only fake keys in security tests (canary, gitleaks negative check).

#### Later (phase 2)

- HTTPS: domain name + Caddy (automatic certificate) or ALB + ACM.
- Images in ECR, deployment via GitHub Actions with OIDC (no more SSH key), infra in CDK or Terraform.
- CloudWatch: log agent, alarm on `/api/health` (Route 53 health check), budget alarm.
- Authentication on write routes (`/api/demo/*`, `approve`, `submit`): nginx basic auth or Cognito.
- SSM Session Manager instead of SSH, automatic secret rotation (Secrets Manager).
- Object Lock retention set per evidence type (T4), bucket replication, dedicated KMS encryption.
- Second standby instance (warm standby) and DNS failover.

#### Claude Code starter prompt

```
You are working on task T8 (AWS, CI and hosting) in TASKS.md (repo root).
1. Read sections 1 and 2 of TASKS.md, then the whole T8 section. Also read backend/settings.py,
   backend/main.py and fixtures/health.json.
2. Modify ONLY the files owned by T8: infra/**, .github/workflows/ci.yml, mk/t8.mk,
   backend/tests/test_t8_*.py. The .gitignore belongs to T0. If you need a change elsewhere (requirements.txt, .gitignore,
   frontend/, backend/ outside tests) or in the contract (section 2), do not edit: write the request
   in docs/contract-requests.md (what, why, who is impacted) and tell me.
3. Start with the tests: backend/tests/test_t8_infra.py, test_t8_check_aws.py (botocore Stubber,
   no network call), test_t8_deploy.py, exactly as described in "Tests that must pass".
   Then write the infra files until make test-t8 is green.
4. Work against the mocks: local .env (NETWORK=local, USE_FIXTURES=true), fake front
   infra/testdata/frontend-stub as long as frontend/package.json does not exist, and only FAKE
   values for any secret test. Do not run any AWS command that creates or deletes resources
   without showing me the command first; region us-east-1 only.
5. Never a secret in a committed file, an image, user-data, or a VITE_* variable.
   No --workers or --reload for uvicorn. No load testing, no Bedrock jailbreak.
6. Before each commit: make test-t8 green (then make docker-smoke and make scan-images if docker
   is available). Push often after each green test, the AWS account is wiped at the end of the event.
```


---
### T9 · Deliverables: README, playbook, compliance, defense sheet, deck, video, pitch

**Goal.** Produce everything the jury reads, sees and hears: the final `README.md`, the response playbook, the compliance note, the one-page defense sheet, the deck outline (8 slides max), the video script (2 to 3 min) and the pitch scripts with Q&A prep. Golden rule: **no invented numbers**. Every number comes from `data/eval/metrics.json`, from `deployments/fuji.json` or from a source listed in `docs/numbers_allowlist.yaml`, and a test checks it. The parts that depend on code (addresses, metrics, response matrix) are **generated** by a script between markers, so they stay up to date without manual edits.

**Depends on.**
- T0 → `TASKS.md` sections 1 and 2, `Makefile`, `.env.example` → available from the start.
- T1 → `deployments/fuji.json` (Fuji addresses) → mock: `fixtures/deployments.example.json` (careful: its `contracts` keys are `Bridge`/`Oracle`, the old format; the authoritative format is the one in 2.3 with `MockBridge`/`MockOracle`).
- T3 → `backend/config/rules.yaml` (for `rules_version`) → mock: the initial YAML from 2.7, copied into `docs/tools/rules.mock.yaml`.
- T4 → `backend/config/playbook.yaml`, `make verify`, anchored decisions → mock: `docs/tools/playbook.mock.yaml` (**verbatim** copy of the YAML in section T4 3.1: `version`, `min_exposure_usd`, `matrix`, `below_min_exposure`) and `fixtures/verify.json`.
- T5 → incident and DORA report, dependency register → mocks: `fixtures/dependencies.json` (valid structure); `fixtures/incident.json` (regenerated by T0: R1 alert and decision `DEC-fuji-45201812-1` at block 45,201,812, see 2.13; if your local copy still contains the old ids D1..D7, it predates the regeneration: rebase).
- T6 → dashboard screenshots → mock: `make backend` + `make frontend` with `USE_FIXTURES=true` (the front end runs on fixtures).
- T7 → `data/eval/metrics.json` (units defined in 2.6: `*_rate` in 0..1, `*_pct_*` in 0..100, `ttd_blocks_*` = -1 if nothing is detected) → mock: `fixtures/metrics.json` (all 0, `notes` contains `FIXTURE`); rendered in PLACEHOLDER mode.
- T8 → public URL of the AWS demo, deployment diagram → mock: `TODO(T8): URL` in the README.
- T2 → `make attack SEED=42` (to film the demo) → mock: the `fixtures/snapshots_attack.jsonl` series (scenario facts).

**Unblocks.** The jury (final submission), the defense, and the whole team (the README is the front door of the repo). T5 reuses `docs/compliance.md` to keep its DORA texts consistent; T6 can link `docs/playbook.md` from the UI.

**Owned files.**
- `README.md` (root, final version, owned by T9 per 1.5; each task provides its paragraph in its PR, T9 assembles; nobody else edits the file)
- `docs/playbook.md`, `docs/compliance.md`, `docs/defense-sheet.md`, `docs/deck-outline.md`, `docs/video-script.md`, `docs/pitch.md`
- `docs/sources.md` (table of verified references), `docs/numbers_allowlist.yaml`, `docs/assets/` (screenshots, diagram)
- `docs/tools/gen_docs.py`, `docs/tools/check_docs.py`, `docs/tools/docs_lib.py`, `docs/tools/fresh_clone_check.sh`, `docs/tools/playbook.mock.yaml`, `docs/tools/rules.mock.yaml`
- `mk/t9.mk`, `backend/tests/test_t9_docs.py`
- Not T9's: `docs/contract-requests.md` (shared), `docs/tasks/` (T0).

**Read before starting.** `TASKS.md` sections 1 (especially 1.2, 1.3, 1.6), 2.2 (initial deployment parameters), 2.3, 2.7, 2.8, 2.9, 2.11; `backend/models.py` (`Decision`, `VerifyResult`, `Incident`, `DoraAssessment`, `DoraCriteria`, `Dependency`, `EvalMetrics`); `fixtures/metrics.json`, `fixtures/verify.json`, `fixtures/dependencies.json`, `fixtures/deployments.example.json`.

#### Inputs

| Input | Format | Provided by | Mock meanwhile |
|---|---|---|---|
| Evaluation metrics | `EvalMetrics` JSON, `data/eval/metrics.json` | T7 | `fixtures/metrics.json` → PLACEHOLDER rendering |
| Fuji addresses | `deployments/fuji.json` (2.3) | T1 | `fixtures/deployments.example.json` → "example addresses" banner |
| Response matrix | `backend/config/playbook.yaml` (schema from section T4 3.1) | T4 | `docs/tools/playbook.mock.yaml` (verbatim copy of the YAML from T4 3.1) |
| Rules version | `backend/config/rules.yaml` → `"sha256:<hex>"` | T3 | `docs/tools/rules.mock.yaml` (YAML from 2.7) |
| Verification result | output of `make verify ID=DEC-…` (`VerifyResult`) | T4 | `fixtures/verify.json` |
| Third-party register (DORA Art. 28) | `GET /api/dependencies` → `Dependency[]` | T5 | `fixtures/dependencies.json` |
| Example DORA report | `GET /api/incidents/{id}/report.md` | T5 | structure of `DoraAssessment` in `models.py` |
| Screenshots and video | PNG in `docs/assets/` | T6 (UI), T2 (scenario) | UI on fixtures (`USE_FIXTURES=true`) |
| README paragraphs per task | "README snippet" section in each task's PR description | T1..T8 | T9 drafts from the `mk/tN.mk` files and gets them reviewed |
| AWS demo URL | text | T8 | `TODO(T8): URL` |

#### Outputs

| Output | Exact format | Consumed by |
|---|---|---|
| `README.md` | English Markdown; sections: Problem, Solution, Architecture, Quickstart (5 commands), Run on Fuji, Fuji contracts (generated block), Results (generated block), Known limitations, Security notes, Repository layout | jury, team |
| `docs/playbook.md` | English Markdown; generated block `gen:playbook` from `playbook.yaml` + `playbook_version` | jury, T6 (link) |
| `docs/compliance.md` | English Markdown; compliance slide content + detailed annex | jury, T5 |
| `docs/defense-sheet.md` | one A4 page, ≤ 600 words | jury |
| `docs/deck-outline.md` | `## Slide 1` … `## Slide 8` max, each slide: title, 3 bullets max, visual, speaker note | team (real deck built from this outline) |
| `docs/video-script.md` | shot table: `# | Duration (s) | Screen | Voice-over`; total 120 to 180 s | team |
| `docs/pitch.md` | Round 1 (5 min) + Q&A 2 min (10 questions); Final (3 min) + Q&A 3 min | team |
| `docs/sources.md` | table `Reference | Official title | URL | Verified (yes/no)` | `check_docs.py` |
| `make docs`, `make docs-check`, `make docs-final`, `make docs-smoke`, `make test-t9` | targets in `mk/t9.mk` | team |

#### Detailed specification

**1. Markers and generator (`docs/tools/docs_lib.py`, `gen_docs.py`).** Live parts sit between `<!-- gen:NAME:start -->` and `<!-- gen:NAME:end -->`. Names: `fuji-addresses` and `results` (README), `playbook` (playbook.md), `metrics` (defense-sheet.md, deck-outline.md Results slide), `versions` (compliance.md).

```python
def file_version(path: Path) -> str                       # "sha256:" + sha256(exact file bytes); same computation as rules_version (2.7)
def replace_block(text: str, name: str, content: str) -> str  # replaces between markers; KeyError if a marker is missing; idempotent
def load_metrics(path: Path | None = None) -> tuple[dict, bool]
    # default data/eval/metrics.json, else fixtures/metrics.json; placeholder=True if fixture file,
    # if an item of notes contains "FIXTURE", or if synthetic.runs_attack == 0
def load_deployment(path: Path | None = None) -> tuple[dict, bool]   # default deployments/fuji.json, else the example (placeholder=True)
def render_addresses_block(dep: dict, explorer: str = "https://testnet.snowtrace.io") -> str
def render_metrics_block(metrics: dict, placeholder: bool) -> str
def render_playbook(playbook_path: Path) -> str
```

CLI: `python docs/tools/gen_docs.py all|readme|playbook|metrics [--metrics P] [--deployments P] [--playbook P]`. Each fallback to a mock writes `WARN t9: using mock <path>` to stderr and inserts `> PLACEHOLDER: generated from <path>, not final.` at the top of the block.

**2. Addresses block.** One row per **unique** address, walking `assets`, `contracts`, `lending` in that order (deduplicate: in the example, `contracts` repeats the tokens). Columns `Name | Address | Explorer`, link `https://testnet.snowtrace.io/address/<address>` (use `explorer` from the JSON if present). On `fuji.json` in 2.3 format as on the example: 9 rows. Add a "Deployed at block" row with `deployed_at_block`. Never show the `roles` section (test key addresses: useless to the jury).

**3. Metrics block.** Units fixed by 2.6 (`EvalMetrics.synthetic`): `detection_rate`, `false_positive_rate` are fractions 0..1, shown × 100 as % with 0 decimals; `saved_pct_mean`, `baseline_saved_pct_mean` are already in 0..100, shown as is (0 decimals) with ` %`; `ttd_blocks_p50/p90` as "N block(s)", and `-1` shows as "not detected" (never "-1 block"). Rows: runs (attack/normal), detection rate, false positive rate, time to detect p50/p90, saved vs baseline, `rules_version` (first 12 hex chars + `…`). In placeholder mode, every value becomes `[[PLACEHOLDER <key>]]` (never "0 %"). `mainnet_replay`: if `null`, write "Mainnet replay: phase 2" and no number. Also copy the `notes` list.

**4. Generated playbook (`docs/playbook.md`).** The file has a hand-written part (roles, documentation) and a `gen:playbook` block:
- header: `playbook_version: sha256:<hex>` = `file_version(backend/config/playbook.yaml)`, identical to the `Decision.playbook_version` field;
- schema read (the one written by T4, section T4 3.1, no other): `version: int`; `min_exposure_usd: number`; `matrix: {critical|high|warning|info: [ {type, mode, per_position?: bool} … ]}` (ordered list, `info: []`); `below_min_exposure: {notify_if_severity_at_least: <severity>}`. `render_playbook` reads only these keys; an unknown or missing key → explicit `ValueError` (better to break the rendering than to document a wrong matrix);
- a table `Severity | Exposure | Actions (in order)`: one row per `matrix` key in the order critical, high, warning, info; Exposure column = `≥ <min_exposure_usd> $` for critical and high, `any` for warning, `—` for info; actions written `<type> (<mode>)` joined by ` → `, with the suffix ` per concerned position` when `per_position: true` (e.g. `EMERGENCY_WITHDRAW (auto) per concerned position`); empty list → `none`;
- a final row `Any | < <min_exposure_usd> $ | NOTIFY (auto) if severity ≥ <notify_if_severity_at_least>, otherwise none` taken from `below_min_exposure`;
- a note under the table, from 2.8 and T4 3.2 (fixed text in the generator): `PAUSE_DEPOSITS` is always listed but becomes `skipped` if deposits are already paused; `EMERGENCY_WITHDRAW` is only created for positions with `withdrawable_now > 0`.
Hand-written part:
- **Who is alerted**: the on-call analyst (`NOTIFY` → SNS topic `SNS_TOPIC_ARN` and/or `ALERT_WEBHOOK_URL`); the treasury signers (`owner` role) for any `pending_approval` action; the compliance officer when an incident is opened (`OPEN_INCIDENT`) for the DORA filing.
- **Automatic**: `NOTIFY`, `PAUSE_DEPOSITS`, `OPEN_INCIDENT`; `EMERGENCY_WITHDRAW` only in critical with exposure ≥ threshold. The guardian key can only tighten: withdrawal **to the vault itself**, never elsewhere (2.2, `emergencyWithdraw`). Describe behaviors exactly as 2.2 fixes them: `pauseDeposits` is idempotent; `emergencyWithdraw` withdraws `min(position, liquidity)`, returns 0 (and emits the event) if there is nothing to withdraw, and fails (`MiniLend: paused`, action `failed`) if the reserve is paused.
- **Human**: `EMERGENCY_WITHDRAW` in high (approval `POST /api/decisions/{id}/approve` with `{"action_index", "approver", "approve"}`), `UNPAUSE_DEPOSITS` (owner only on-chain), `FULL_EXIT` (outside the MVP matrix, always manual), DORA submission (`POST /api/incidents/{id}/submit`).
- **How it is documented**: `Decision` (alerts, `matrix_cell`, `rationale`, `inputs_hash`, `rules_version`, `playbook_version`), `record_hash` anchored in `EvidenceRegistry` (`anchor_tx`, `anchor_block`), incident timeline (`TimelineEvent.kind` ∈ alert, decision, action, chain, human, dora), verification `make verify ID=DEC-…`.
- **Typical run** on the 1.2 scenario, phase by phase, citing only facts from 2.2 and `fixtures/snapshots_attack.jsonl`.

**5. `docs/compliance.md`.** Two parts: (a) the exact slide text (≤ 80 words), (b) the annex. Every cited article has its row in `docs/sources.md` with its EUR-Lex ELI link (`https://eur-lex.europa.eu/eli/reg/2022/2554/oj` DORA; `https://eur-lex.europa.eu/eli/reg_del/2024/1772/oj` classification RTS; `https://eur-lex.europa.eu/eli/reg_del/2025/301/oj` RTS on report content and deadlines). Annex content:
- **DORA Art. 17** (ICT-related incident management process) → detection R1..R5, recording of every alert and decision. **Art. 18** (classification) + **RTS 2024/1772 Art. 8** (classification as a major incident) and **Art. 9** (materiality thresholds) → `DoraCriteria` (including the three optional fields of Art. 9(1) added in 2.6: `counterparts_affected_pct`, `transactions_affected_count_pct`, `relevant_clients_affected`), `thresholds_met`, `is_major`, `legal_basis`. **Art. 19** (reporting of major incidents) + **Delegated Regulation 2025/301** (deadlines) → `DoraDeadlines`: initial notification 4 h after classification and at the latest 24 h after becoming aware, intermediate report 72 h after the initial notification, final report 1 month after the last intermediate report. Find and cite the exact article of 2025/301 that sets these deadlines (expected: Art. 5), after reading the text.
- **Who files**: the client financial entity, not us; the platform pre-fills, a human validates and submits (`submitted_by`).
- **DORA Art. 28** (register of information on ICT third-party service providers) → dependencies page (`Dependency`: `kind`, `criticality`, `supports`, `fallback`). One sentence: we are ourselves an ICT third-party service provider for the client.
- **AML/CFT**: "Fund tracing (where the forged rsETH come from, where the borrowed WETH goes) is phase 2; the MVP does no screening."
- **MiCA** (Regulation (EU) 2023/1114): a single cautious sentence, without claiming compliance: the tool is the client's internal risk management, the MiCA analysis depends on its status.
- **AI Act** (Regulation (EU) 2024/1689): in the MVP the AI (Bedrock, `BEDROCK_MODEL_ID`) only drafts one paragraph of the report; the sections concerned are listed in `ai_drafted_sections` and displayed as such; all decisions come from versioned deterministic rules; a human submits. Without `BEDROCK_MODEL_ID`, a deterministic template replaces the AI. Do not cite any AI Act article without having read it.
- **How an auditor verifies** (`gen:versions` block + commands): `make verify ID=DEC-fuji-…` (id = block of the alerts snapshot, e.g. `DEC-fuji-45201812-1` in the fixtures) → first line `MATCH`, exit code 0, line `anchored: yes (block …, tx …)` (API equivalent: `VerifyResult.match == true` and `anchored == true`); `cast call <EvidenceRegistry> "anchoredAt(bytes32)(uint256)" <record_hash> --rpc-url $RPC_URL` → returns `anchor_block`; snowtrace link of `anchor_tx`; `shasum -a 256 backend/config/rules.yaml` → equal to the alerts' `rules_version` (without the `sha256:` prefix). Paste a real Fuji verify output (mock: `fixtures/verify.json`, marked PLACEHOLDER).

**6. `docs/defense-sheet.md` (one page).** Four blocks: (1) NIST CSF 2.0, columns `Function | Subcategory | What we do`, functions Detect / Respond / Recover; candidates to check against the official text (NIST CSWP 29) before use: `DE.CM-09`, `DE.AE-02`, `DE.AE-04`, `DE.AE-08`, `RS.MA-01`, `RS.MI-01`, `RS.AN-06`, `RS.AN-07`, `RS.CO-02`, `RC.RP-01`, `RC.CO-03`, and `GV.SC-04` for the third-party register; drop any id whose title does not fit. (2) Threats: OWASP Smart Contract Top 10 (2025 edition, candidates `SC01:2025` access control for `forgedRelease` callable by anyone, `SC03:2025` logic errors), MITRE ATLAS `AML.T0051` (prompt injection in on-chain data sent to Bedrock), MITRE ATT&CK: only if a technique really fits (candidate to check: `T1565`, Data Manipulation), otherwise say "ATT&CK Enterprise covers DeFi logic poorly". (3) Results: `gen:metrics` block only. (4) Limitations: simulated contracts, test chain, a single attack family, mainnet replay in phase 2, same-block attack cannot be blocked.

**7. `docs/deck-outline.md` (8 slides max).** `## Slide 1 · Problem`, `2 · Solution`, `3 · Live demo`, `4 · Architecture`, `5 · Results` (`gen:metrics` block), `6 · Compliance` (text from 5a), `7 · Business model`, `8 · Roadmap & team`. Each slide: ≤ 3 bullets, visual (`docs/assets/...`), speaker note ≤ 40 words. Business model: B2B SaaS for crypto treasuries subject to DORA (fintechs, asset managers, corporate treasuries), subscription by tier of monitored assets, optional compliance module, protocol adapters. Any price is a **hypothesis** labeled as such and listed in the allowlist with `source: hypothesis`. Team slide: `[member 1..4]`, no employer.

**8. `docs/video-script.md`.** Table `# | Duration (s) | Screen | Voice-over`, 8 to 12 shots, total 120 to 180 s. Order: hook (the problem in one sentence), calm dashboard, `make attack SEED=42` / demo button, critical R1 alert and its explanation, decision (pause + emergency withdrawal, snowtrace links), comparison with the stuck passive supplier (`lend-eth` WETH position at 0% withdrawable in the attack series), incident + DORA draft, `make verify`, conclusion. Shoot on Fuji if possible, otherwise locally and say so.

**9. `docs/pitch.md`.** Round 1: 5-min script (≤ 700 words, about 140 words/min), split like the deck; Q&A 2 min: 10 hard questions, answer ≤ 50 words each. The 10: (1) difference from existing on-chain monitoring tools; (2) cost of a false positive; (3) compromised guardian key; (4) attacker faster than us / same block; (5) would it have worked on the real incident (honest answer: mainnet replay in phase 2); (6) why anchor on a blockchain; (7) who reports to the authority, are we subject to DORA; (8) role of AI and hallucinations; (9) moving to real protocols (adapters); (10) who pays and how much. Final: 3-min script (≤ 420 words) + Q&A 3 min (reuse the 10 and add 3 follow-up questions).

**10. README.md.** Quickstart in exactly 5 commands:
```
git clone <repo> && cd <repo>
cp .env.example .env
make setup
make demo            # anvil + deploy + seed + backend (engine on) + frontend
make attack SEED=42  # in a second terminal; then open the dashboard
```
`make demo` starts the backend with `ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false` (2.11): the README says so, so nobody thinks they are seeing fixtures. Then "Verify a decision": `make verify ID=<id from the dashboard>`. "Run on Fuji" section: variables in `.env` (the root `Makefile` does `-include .env` and exports the variables, 2.11): `NETWORK=fuji`, `RPC_URL`, keys per role (2.1), `USE_FIXTURES=false`, `ENGINE_ENABLED=true`, `DRY_RUN_ACTIONS=false`; then reuse the committed `deployments/fuji.json` (normal case) or `make deploy FORCE=1` (mandatory if a fuji deployment already exists; addresses change), `make seed`, `make backend`, `make frontend`, `make attack SEED=42` (variants `default`, `slow`, `usdc` via the API; `seed = 0` gives the default parameters without randomness). Security notes: no keys in the repo, `gitleaks`, restricted-power guardian, `unpauseDeposits` owner only, synthetic data, unaudited contracts. Known limitations: in addition to the defense sheet list, `EvidenceRegistry` has no access control in the MVP (anyone can anchor; we verify the hash, not the author), and an anchoring cannot be undone.

**11. Checker (`docs/tools/check_docs.py`).**
```python
def extract_numbers(md: str) -> list[tuple[int, str]]   # (line, normalized number)
def allowed_numbers(metrics: dict, dep: dict, allowlist: list[dict]) -> set[str]
def find_secrets(md: str) -> list[str]
def find_reference_ids(md: str) -> set[str]               # NIST, ATT&CK, ATLAS, OWASP SC
def check(paths: list[Path], final: bool) -> list[str]    # list of problems, empty = OK
```
`extract_numbers` ignores: code blocks, inline code, URLs, HTML comments, reference ids (`DE.AE-08`, `T1565`, `AML.T0051`, `SC01:2025`), article numbers (`Art. 19`, `9(1)(a)`), regulation numbers (`2022/2554`, `2024/1772`, `2025/301`, `2023/1114`, `2024/1689`), `Slide N` and `Q N` headings, `m:ss` timecodes, the `#` and `Duration (s)` columns of the video table, ids `R1`..`R5`, `T0`..`T9`. Normalization: strip `,`, thin spaces, `$`, `%`, `bps`; `19.4` and `19,4` are equal. `allowed_numbers` contains: raw values from `metrics.json` and their displayed formats, `deployed_at_block`, and the `value` entries of `docs/numbers_allowlist.yaml`. Allowlist format:
```yaml
- { value: "1325000", source: "TASKS.md 2.2: 150 WETH and 100 WETH at 2500 $ + 400000 + 300000 USDC", where: [README.md, docs/pitch.md] }
- { value: "19.4", source: "fixtures/snapshots_attack.jsonl block 45201812: backing_ratio_bps 1935", where: [docs/playbook.md] }
- { value: "72", source: "Delegated Regulation (EU) 2025/301, intermediate report deadline", where: [docs/compliance.md] }
```
`find_secrets` flags: `0x` + 64 hex outside a `…/tx/` URL or a `record_hash`/`anchor_tx`/`stored_hash`/`recomputed_hash` line, `AKIA[0-9A-Z]{16}`, `BEGIN .*PRIVATE KEY`, `_PK=` followed by a value, `aws_secret_access_key`. Forbidden terms (employers): read from the `T9_FORBIDDEN_TERMS` environment variable (comma-separated, never committed). `final=True` adds: no `[[PLACEHOLDER`, no `TODO`, no `PLACEHOLDER:` banner.

**12. `mk/t9.mk`.** Never redefines `NETWORK` (2.11). `T9_STRICT` separates two test levels: non-strict (default, called by `make test`) and strict (consistency of the docs with `backend/config/playbook.yaml`, `deployments/fuji.json` and `data/eval/metrics.json`, run only by `make docs-final`). That way a T1, T4 or T7 commit that changes an address, the matrix or the metrics does not break `make test` on `main`; T9 regenerates the docs afterwards.
```make
docs:        ; python docs/tools/gen_docs.py all
docs-check:  ; python docs/tools/check_docs.py
docs-final:  ; python docs/tools/gen_docs.py all && python docs/tools/check_docs.py --final && T9_STRICT=1 python -m pytest -q backend/tests/test_t9_docs.py
docs-smoke:  ; bash docs/tools/fresh_clone_check.sh
test-t9:     ; T9_STRICT=0 python -m pytest -q backend/tests/test_t9_docs.py
```
`test-t9` forces `T9_STRICT=0` (the root `Makefile` exports `.env`: a value left over in `.env` must not make `make test` strict). In `test_t9_docs.py`, strict tests carry `strict = pytest.mark.skipif(os.environ.get("T9_STRICT") != "1", reason="strict docs checks: make docs-final")`.

`fresh_clone_check.sh`: clones into a temporary folder, `cp .env.example .env`, `make setup`, `make demo` in the background, waits for `GET http://127.0.0.1:8000/api/health` = 200 (120 s max), then `GET /api/state` = 200 (503 `no snapshot yet` while the engine has not read any block: retry), `POST /api/demo/attack {"seed":42,"variant":"default"}` (409 = run already in progress: step fails), waits for a decision in `GET /api/decisions` (120 s max), runs `make verify ID=<first id>`, checks exit code 0 and first line `MATCH`, kills the processes, prints `SMOKE OK` or the step that failed.

#### Tests that must pass

Command: `pytest backend/tests/test_t9_docs.py` (never `-k`), via `make test-t9` (= `T9_STRICT=0 python -m pytest -q backend/tests/test_t9_docs.py`, non-strict tests only, called by `make test`). Tests marked **[strict]** (T9-03, T9-04, T9-06) only run under `make docs-final` (or `T9_STRICT=1`): they compare the committed docs with files produced by other tasks, which change without T9 knowing. The tests load `docs/tools/docs_lib.py` and `check_docs.py` via `importlib` (the `docs/` folder is not a package).

- **T9-01** `test_deliverables_exist` (unit). The 7 deliverables exist, are non-empty, and contain their mandatory headings (README: `## Quickstart`, `## Run on Fuji`, `## Known limitations`, `## Security notes`; playbook: `## Who is alerted`, `## What is automatic`, `## What stays human`, `## How it is documented`). Expected: 0 missing.
- **T9-02** `test_playbook_render_from_mock` (unit). Setup: `render_playbook(docs/tools/playbook.mock.yaml)` (verbatim copy of the YAML from T4 3.1). Expected: the critical row contains exactly `NOTIFY (auto) → PAUSE_DEPOSITS (auto) → EMERGENCY_WITHDRAW (auto) per concerned position → OPEN_INCIDENT (auto) → UNPAUSE_DEPOSITS (human)`; the high row contains `EMERGENCY_WITHDRAW (human) per concerned position`; the warning row contains only `NOTIFY (auto)`; the info row contains `none`; a `< 1000 $` row contains `NOTIFY (auto) if severity ≥ high`; the header contains `playbook_version: sha256:` followed by 64 hex equal to the file's `file_version`. Rendered twice: identical (idempotence). Negative case: a YAML without `matrix` → `ValueError`.
- **T9-03** **[strict]** `test_playbook_doc_up_to_date` (integration). Regenerate `docs/playbook.md` in memory from `backend/config/playbook.yaml` (explicit failure if it does not exist: in strict mode the mock is not accepted): identical to the committed file, and the displayed `playbook_version` = `file_version(backend/config/playbook.yaml)`.
- **T9-04a** `test_addresses_block_render` (unit, non-strict). Setup: `fixtures/deployments.example.json`. Expected: 9 address rows, each with the link `https://testnet.snowtrace.io/address/<address>`; no address from `roles`; a `45201700` row.
- **T9-04** **[strict]** `test_readme_addresses_match_deployment` (integration). `deployments/fuji.json` must exist; every address in the README's `gen:fuji-addresses` block is present in that file (excluding `roles`) and vice versa; `deployed_at_block` identical; no `PLACEHOLDER:` banner in the block.
- **T9-05** `test_metrics_placeholder_mode` (unit). Setup: `fixtures/metrics.json`. Expected: `placeholder is True`, the block contains `[[PLACEHOLDER detection_rate]]` and contains neither `0 %` nor `0.0`. Second case, temporary file with `runs_attack: 10, runs_normal: 10, detection_rate: 1.0, false_positive_rate: 0.0, ttd_blocks_p50: 1, ttd_blocks_p90: 2, saved_pct_mean: 100.0, baseline_saved_pct_mean: 0.0`, `notes: []`: `placeholder is False`, the block contains `100 %` (detection rate 1.0 × 100 and saved 100.0 as is), `1 block`, `2 blocks`, `Mainnet replay: phase 2`. Third case: `ttd_blocks_p50: -1, ttd_blocks_p90: -1` → `not detected`, never `-1`.
- **T9-06a** `test_numbers_checker` (unit, non-strict). The text `We save 87 % of funds.` with an empty allowlist returns a problem mentioning `87`; the same text with `{value: "87", …}` in the allowlist returns none; `Art. 19`, `2022/2554`, `R1`, `0:42` are not extracted.
- **T9-06** **[strict]** `test_numbers_traceable` (integration). `check(...)` on README and `docs/*.md` (excluding `docs/tasks/`, `docs/contract-requests.md`) with the real `data/eval/metrics.json` and `deployments/fuji.json` (explicit failure if missing): 0 unknown numbers.
- **T9-07** `test_no_secrets` (unit + integration). All deliverables: 0 alerts. Negative case: `GUARDIAN_PK=0x` + 64 `a` characters is detected; a link `https://testnet.snowtrace.io/tx/0x` + 64 hex is not.
- **T9-08** `test_forbidden_terms` (integration). Skip if `T9_FORBIDDEN_TERMS` is not set; otherwise 0 occurrences (case-insensitive) in all deliverables.
- **T9-09** `test_deck_max_8_slides`. Number of `^## Slide \d+` between 7 and 8; titles containing `Live demo`, `Results`, `Compliance`, `Business model`.
- **T9-10** `test_video_duration`. Sum of the `Duration (s)` column between 120 and 180; 8 to 12 shots.
- **T9-11** `test_defense_sheet_one_page`. ≤ 600 words (excluding markers), ≤ 70 non-empty lines; contains `Detect`, `Respond`, `Recover`, `Limitations`.
- **T9-12** `test_reference_ids_verified`. Every id returned by `find_reference_ids` over all deliverables exists in `docs/sources.md` with `Verified` = `yes` and an official URL (`nist.gov`, `attack.mitre.org`, `atlas.mitre.org`, `owasp.org`). `docs/sources.md` also contains the 3 EUR-Lex ELI links from 5.
- **T9-13** `test_pitch_structure`. Section `## Round 1 (5 min)` ≤ 700 words; exactly 10 `### Q` headings in `## Round 1 Q&A`; section `## Final (3 min)` ≤ 420 words.
- **T9-14** smoke (manual, before submission). `make docs-smoke` on a fresh clone: last line `SMOKE OK`.
- **T9-15** final (manual, before submission). `make docs-final`: exit code 0 (regeneration, `check_docs.py --final`, then strict tests T9-03, T9-04, T9-06 with `T9_STRICT=1`; so real T7 metrics, real T1 addresses, real T4 playbook). Open every snowtrace link in the README by hand: the address page exists.
- **T9-16** citation review (manual). For each cited regulatory article, open the ELI link and tick the `Verified` column in `docs/sources.md`; an article that cannot be found is removed from the text.

#### Definition of done

- [ ] `make test-t9` green (non-strict tests: T9-01, T9-02, T9-04a, T9-05, T9-06a, T9-07 to T9-13; T9-03, T9-04, T9-06 skipped); T9-08 run at least once with `T9_FORBIDDEN_TERMS` set.
- [ ] `make docs-final` green: no PLACEHOLDER or TODO left, real metrics from `data/eval/metrics.json`, strict tests T9-03, T9-04, T9-06 green.
- [ ] `make docs-smoke` prints `SMOKE OK` on a fresh clone.
- [ ] README: 5 commands, Fuji section, Fuji addresses with snowtrace links, limitations, security notes, AWS URL (T8).
- [ ] Playbook generated from the real `backend/config/playbook.yaml`; `playbook_version` identical to the decisions' one.
- [ ] Compliance: real `make verify` output on Fuji pasted; every article verified in `docs/sources.md`.
- [ ] Deck ≤ 8 slides, video 120 to 180 s, defense sheet on one printed A4 page, pitch timed out loud (5 min and 3 min).
- [ ] Each task has reviewed the README paragraph that concerns it.

#### Known pitfalls

- **Invented "catchy" numbers.** No "99% detection" until T7 has produced `metrics.json`. PLACEHOLDER mode exists for that; otherwise `make docs-final` blocks the submission.
- **`fixtures/metrics.json` is 0 everywhere.** Showing "0% false positives" would be false and flattering: test T9-05 forbids it.
- **Metric units.** Fixed by 2.6: `*_rate` in 0..1 (multiply by 100 for display), `*_pct_*` already in 0..100 (do not multiply again), `ttd_blocks_*` = -1 when nothing is detected (show "not detected"). A "10000%" or "1%" of funds saved betrays a double conversion.
- **API fixtures.** The regenerated fixtures (2.13) put the R1 alert and `DEC-fuji-45201812-1` at block 45,201,812; if your copy of `alerts.json`, `decisions.json` or `incident.json` still contains D1..D7, it is stale (rebase). Even up to date, a fixture is not a source of numbers for the jury: every number goes through the allowlist with its source. Rules are named `R1_BACKING_DROP` to `R5_RESERVE_FROZEN`.
- **Strict tests in `make test`.** Never remove the `skipif` from T9-03, T9-04, T9-06: they depend on other tasks' files and would break `main` on every T1 redeployment, T4 matrix change or new T7 evaluation. They run in `make docs-final`.
- **Decision ids.** They carry the block of the alerts snapshot (`DEC-<network>-<block>-<n>`), not the block where transactions execute: in the docs, cite `DEC-fuji-45201812-1` for the fixtures, and the real id copied from the dashboard for Fuji.
- **`deployments.example.json` ≠ 2.3 format** (`Bridge`/`Oracle` instead of `MockBridge`/`MockOracle`): the generator walks the keys present, with no hard-coded list.
- **64-hex hash = tx or key?** A transaction hash has the same shape as a private key: only write them in `…/tx/` links or named fields (see 11).
- **Listing employers in a committed file reveals them.** Hence the environment variable.
- **Citations.** Only cite a paragraph (e.g. `Art. 19(4)`) if you have read it; otherwise cite the article alone. Do not attribute the 4 h / 72 h / 1 month deadlines to DORA itself: they come from Delegated Regulation 2025/301.
- **The real Kelp/Aave incident.** Assert nothing about its amounts or timeline without a verified public source listed in `docs/sources.md`; say "synthetic replay inspired by".
- **Demo time.** On Fuji, about 2 s per block: the video must cut the waits, the live demo must hold without waiting for the protocol freeze.
- **README in English, internal docs in French** (1.6 rule 7): all jury deliverables are in English.

#### Later (phase 2)

- Mainnet replay results (`mainnet_replay` in `metrics.json`) in the README, the deck and the defense sheet.
- Real AML/CFT section (fund tracing, screening).
- Automatic PDF export (deck, defense sheet) and one-page layout check.
- Full NIST CSF 2.0 mapping (Identify, Protect, Govern) and extended ATT&CK/ATLAS once advanced rules exist.
- Multi-protocol playbook and on-call levels (timed escalation).
- Automatic checking of snowtrace and EUR-Lex links in CI (T8).

#### Claude Code starter prompt

```
You are working on task T9 (deliverables: README, playbook, compliance, defense sheet,
deck, video, pitch) from the TASKS.md file at the repo root.
1. Read TASKS.md sections 1 and 2 in full, then the T9 section in full. Read backend/models.py
   (Decision, VerifyResult, Incident, DoraAssessment, Dependency, EvalMetrics) and the fixtures
   metrics.json, verify.json, dependencies.json, deployments.example.json.
2. Modify ONLY the files listed in T9's "Owned files" (README.md, docs/ except
   docs/tasks/ and docs/contract-requests.md, mk/t9.mk, backend/tests/test_t9_docs.py).
   If you need a change elsewhere or in the contract (section 2), do not edit:
   write the request in docs/contract-requests.md and tell me.
3. Start by writing backend/tests/test_t9_docs.py (tests T9-01 to T9-13; T9-03, T9-04,
   T9-06 marked strict: skipped unless T9_STRICT=1), then
   docs/tools/docs_lib.py, gen_docs.py, check_docs.py, mk/t9.mk, then the documents.
4. Work against the mocks: fixtures/metrics.json (PLACEHOLDER mode),
   fixtures/deployments.example.json, docs/tools/playbook.mock.yaml (verbatim copy of the YAML from T4 3.1),
   fixtures/verify.json. Do NOT invent ANY number: every number comes from metrics.json,
   deployments/fuji.json or docs/numbers_allowlist.yaml (with its source).
5. Do not write any NIST/ATT&CK/ATLAS/OWASP identifier or legal article without asking me to
   verify it against the official source; add it to docs/sources.md with Verified = no.
6. Jury deliverables in English. No secrets, no employer names, no personal names.
7. Before each commit: make test-t9 and make docs-check must be green; push often
   after each green test. make docs-final (strict) only once T1, T4 and T7 have delivered.
```


---

## 4. Integration: assembly order and end-to-end tests

### 4.1 Assembly order

1. **T0** is merged first. All branches start from that commit.
2. **In parallel, each on their own mocks:**
   - T1 (local deployment);
   - T3 (rules on recorded series);
   - T4 (dry-run);
   - T5 (hand-built decisions);
   - T6 (fixtures);
   - T8 (infra);
   - T9 (drafts).
3. **T2** starts as soon as T1's `make deploy NETWORK=local` works.
4. **E2E-1 (local)** as soon as T1, T2, T3 and T4 are merged. T5 and T6 plug into it.
5. **T1 on Fuji**, then **E2E-2 (Fuji)**.
6. **T8** puts the Fuji version on AWS, then **E2E-3 (AWS)**.
7. **T7** runs the evaluation on the local chain (frozen thresholds) and produces `data/eval/metrics.json`.
8. **T9** replaces all provisional numbers with those from `metrics.json` and `deployments/fuji.json`.

Merge rule: a PR is merged only if `make test` is green on the branch rebased on `main`. In case of a conflict on a file, the task that owns the file decides.

### 4.2 E2E-1: end to end on the local chain

```
make chain                                   # terminal 1
NETWORK=local make deploy seed               # terminal 2
NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false make backend   # terminal 3
make frontend                                # terminal 4
make attack SEED=42                          # terminal 2
```

Expected results:

| # | Check | Expected |
|---|---|---|
| 1 | `GET /api/alerts` | a critical `R1_BACKING_DROP` alert at most 2 blocks after the `forgedRelease` block (block read from `data/runs/<run_id>.json`) |
| 2 | `GET /api/decisions` | a decision with `NOTIFY`, `PAUSE_DEPOSITS`, 4 × `EMERGENCY_WITHDRAW`, `OPEN_INCIDENT` with status `executed` (with `tx_hash`), and `UNPAUSE_DEPOSITS` as `pending_approval` |
| 3 | `GET /api/state` | `vault.deposits_paused = true`, `positions = []`, `idle_balances` = 250 WETH and 700,000 USDC, `totals.at_risk_usd = 0` |
| 4 | after protection | no more R2 to R5 alerts: the vault has no exposure left |
| 5 | `make verify ID=<decision id>` | `MATCH`, `anchored = true` |
| 6 | `make tamper …` then `make verify` | `MISMATCH` with at least one readable difference |
| 7 | `GET /api/incidents` | a `contained` incident, DORA `is_major = true`, thresholds 9(1) and 9(4), deadlines computed |
| 8 | dashboard | critical badge, empty positions, incident, Verify button → MATCH, attack run log |

### 4.3 E2E-2: end to end on Fuji

Same commands with `NETWORK=fuji` and a provider `RPC_URL`. Use the default attack (one tranche every 8 s).

Expected:
- points 1 to 8 of E2E-1;
- every `tx_hash` opens on `https://testnet.snowtrace.io`;
- the anchoring transaction is visible;
- the addresses in `deployments/fuji.json` are committed.

### 4.4 E2E-3: demo hosted on AWS

- **Public pages**: the public URL serves the dashboard, and `GET /api/health` returns `network = fuji` and `rpc_ok = true`.
- **Attack**: a click on "Launch attack" triggers the scenario.
- **Notification**: an SNS email arrives within a minute.
- **Evidence**: the evidence is stored in the S3 bucket.
- **Report**: the DORA report is displayed, with the description drafted by Bedrock or the fallback template.
- **Plan B**: `make demo` locally and the recorded video.

### 4.5 Demo walkthrough

1. The vault is healthy: positions on `lend-eth` and `lend-avax`, risk `info`.
2. A juror clicks "Launch attack". The random seed is displayed, which shows the attack is not scripted for us.
3. Critical R1 alert, with its quantified sentence. In the following blocks: deposits paused and all exposed positions pulled back to the vault. The snowtrace links are visible.
4. The `lend-eth` chart then shows liquidity dropping to zero: a passive supplier would be stuck, we are not.
5. Incident opened, DORA classification proposed, deadlines displayed, report pre-filled. A human clicks "Submit".
6. "Verify" returns MATCH. We tamper with the evidence live, and the result switches to MISMATCH.

---

## 5. Later (phase 2, do not build in the MVP)

- **AI agent** that proposes allocations; "guaranteed rules" vs "guidelines" setting; membrane between agents (answer to ASI07).
- **Instructions and allowlist** sealed by a Merkle root, real Safe and guardian module, EIP-712 mandates.
- **Advanced detection rules**:
  - collateral inflow;
  - bait yield (yield rising while liquidity falls);
  - dedicated contagion rule;
  - oracle deviation;
  - borrow velocity;
  - diff of governance changes.
- **Replay of the real Aave incident** of April 18, 2026, on Ethereum data, and measurement of false positives on normal days.
- **Tracing the attacker's funds**, for the AML/CFT part.
- **Robustness**:
  - two independent RPCs that must agree on the block hash;
  - conditions re-checked inside the transaction (anti-TOCTOU);
  - S3 Object Lock.
- **Real exit costs** (slippage), and optimized partial exit.
