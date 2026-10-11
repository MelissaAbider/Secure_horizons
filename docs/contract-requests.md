# Contract change requests

Template: task, requested change, reason, impacted tasks, status.

## CR-001 · Provisional `backend/models.py` from T4

- **Task:** T4 (branch `Adam-(T4,-T5)`)
- **Change:** `backend/models.py` written from TASKS.md 2.6, sub-objects taken from the T3/T5/T6 sheets (`DoraCriteria`, `DoraDeadlines`, `TimelineEvent`, `SeriesPoint`, `StateResponse`). `Health`, `DemoRun`, `RunRecord`, `EvalMetrics` are not included.
- **Reason:** the T0 skeleton is not on `main`; T4 cannot build `Alert`, `Snapshot`, `Decision` without it.
- **Impacted:** T0 (please start from this file instead of writing a second version), all Python tasks.
- **Status:** open

## CR-002 · Provisional `backend/settings.py` from T4

- **Task:** T4 (branch `Adam-(T4,-T5)`)
- **Change:** minimal `backend/settings.py`: `NETWORK`, `CHAIN_ID`, `EXPLORER_URL`, `USE_FIXTURES`, `DRY_RUN_ACTIONS`, `AWS_REGION`, `SNS_TOPIC_ARN`, `ALERT_WEBHOOK_URL`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID`, `ROOT`, `CONFIG_DIR`, `DATA_DIR`, `FIXTURES_DIR`. No private keys, no `private_key(role)`, no `bot_pks()`, no `RPC_URL`.
- **Reason:** T4 reads `CONFIG_DIR`, `DATA_DIR`, `DRY_RUN_ACTIONS` and the AWS variables.
- **Impacted:** T0 (complete it per T0 step 4), all Python tasks.
- **Status:** open

## CR-003 · `.gitignore` entries for runtime data

- **Task:** T4 (branch `Adam-(T4,-T5)`)
- **Change:** add the T0 step 13 entries, at least `data/runtime/`, `data/evidence/`, `data/runs/`, `data/reports/`, `deployments/local.json`.
- **Reason:** `make decision-demo` and `make verify` write `data/evidence/*.json` and `anchors.json`; they must not be committed.
- **Impacted:** T0, T2, T4, T5.
- **Status:** open

## CR-004 · Provisional T0 shim to run T4 + T5 end-to-end

- **Task:** T4/T5 (branch `Adam-(T4,-T5)`)
- **Change:** minimal T0 files, each marked `T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.`:
  - `backend/store.py`: `Store` (RLock, in-memory, JSONL append under `DATA_DIR/runtime/<NETWORK>/`, `reset()` + `generation`), singleton `store`. Ordering follows the T4/T5 `FakeStore`.
  - `backend/chain.py`: `w3`, `load_deployment`, `load_abi`, `contract`, `token`, `lending`, `vault`, `bridge`, `oracle`, `registry`, `account`, `bot_accounts`, `send`, `explorer_tx`; web3 imported lazily. Assumed deployment JSON shape (`lending[i].address`, `contracts.{vault,oracle,registry,bridge}`) and ABI names (`Vault`, `LendingPool`, `PriceOracle`, `EvidenceRegistry`, `Bridge`, `RsETH`, `MockERC20`) are in its docstring, to be confirmed by T1.
  - `backend/engine.py`: stub for T3 (no detection) plus a shim-only `Engine.inject(alerts, snapshot)` that calls subscribers synchronously.
  - `backend/main.py`: FastAPI app, CORS `*`, T4 + T5 routers under `/api`, `/api/health`, `wire(store)` (engine -> responder -> incidents), engine loop only if `ENGINE_ENABLED`.
  - `backend/t0_shim_demo.py` (`make t4t5-demo`).
  - `backend/settings.py` extended: `RPC_URL`, `RPC_FALLBACK_URL`, `ENGINE_ENABLED`, `POLL_INTERVAL_S`, `DEPLOYMENTS_FILE`, `ABI_DIR`, `private_key(role)`, `bot_pks()` (env keys, or derived from the public anvil mnemonic on `local` only; never stored).
  - Root `Makefile` (`help`, `setup`, `backend`, `test`) and `mk/t0.mk` (`test-t0`, `t4t5-e2e`, `t4t5-demo`).
  - `backend/tests/test_t0_shim_*.py`, including the T4 + T5 end-to-end test.
  - `.gitignore`: CR-003 entries applied.
  - No `fixtures/` on purpose: `test_t4_*` and `test_t5_*` switch to `fixtures/snapshots_attack.jsonl` / `decisions.json` / `incident.json` when they exist, and the T4 and T5 synthetic series differ slightly; a shim fixture would silently change the data under the existing tests. Run the shim backend with `USE_FIXTURES=false`.
- **Reason:** test T4 + T5 together, in dry-run, without T0/T1/T2/T3.
- **Impacted:** T0 (replace these files, keep the store/engine/main signatures T4/T5 rely on), T1 (deployment JSON shape, ABI names), T3 (engine).
- **Status:** open

## CR-005 · Dependency and shared test fixture added on branch `Adam-(T4,-T5)`

- **Task:** T4 / T5 (branch `Adam-(T4,-T5)`)
- **Change:** (1) add `fpdf2==2.8.9` to `requirements.txt` (used by `backend/dora_pdf.py`, DORA report as PDF); (2) `backend/tests/conftest.py` (autouse fixture) blanks `ALERT_WEBHOOK_URL`, `SNS_TOPIC_ARN`, `EVIDENCE_BUCKET`, `BEDROCK_MODEL_ID` so no test ever reaches Discord or AWS when a real `.env` is present; (3) new optional `.env` variables for e-mailing the DORA draft: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_ALLOWED_RECIPIENTS` (to add to `.env.example`, empty).
- **Reason:** `requirements.txt`, `conftest.py` and `.env.example` belong to T0; there is no `requirements.txt` on `main` yet.
- **Impacted:** T0, T8 (Docker image needs fpdf2; SMTP secrets go to SSM, never in the image).
- **Status:** open

## CR-006 · Agent routes and replay in the T0 shim

- **Task:** agent (branch `Adam-(T4,-T5)`)
- **Change:** `backend/main.py` includes `backend/api/agent.py` (`POST /api/agent/propose`, `GET /api/agent/proposals`) and a shim-only `POST /api/demo/replay` (dry-run only: R1 at block 45201812 then the reacted series). `requirements.txt` added (runtime only, plus `eth-hash[pycryptodome]` for keccak and `python-dotenv`).
- **Reason:** run the agent on an EC2 VM with Bedrock and populate the API without a chain.
- **Impacted:** T0 (keep or move these routes), T8 (VM setup).
- **Status:** applied on the branch, informational
