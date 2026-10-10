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

## CR-003 · KelpDAO bridge integrity fields for T3

- **Task:** T3 (`feature/t3-kelpdao-surveillance`)
- **Change:** add `bridge_source_locked`, `bridge_destination_released`, `bridge_source_nonce`, `bridge_destination_nonce`, and `bridge_paused` to `TokenSnapshot`; replace the generic R1–R5 ids with the KelpDAO causal rule set in TASKS.md 2.7.
- **Reason:** the root signal is a forged cross-chain release without a canonical source event, not a market-price or simple backing-ratio change.
- **Impacted:** T0 fixtures/types, T1 MockBridge, T2 scenario phases, T3 rules, T4–T7 labels and tests.
- **Status:** implemented on T3 branch; requires team contract approval
