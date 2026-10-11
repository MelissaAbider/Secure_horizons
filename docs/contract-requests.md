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

## CR-004 · T3 evidence qualification and hardened rule semantics

- **Task:** T3 only; no changes to shared models, T1/T2 contracts/scenarios, T4 response code or fixtures in this hardening.
- **Implemented locally:** rule version 3, documented in `docs/product/THRESHOLDS.md`. Rule IDs and Alert fields are unchanged. Live R1 counter mismatch is warning/unverified, uncorroborated R2 is warning, R3 also checks persistent utilization, R4 uses exact effective amounts, R5 covers ongoing bridge/reserve containment at startup. Unchanged attack snapshots now yield eight alerts because bridge pause was previously missed.
- **Integration requirement:** a global R5 alert has `deployment_id=null`, `asset=rsETH`, `metrics.scope=bridge`. Consumers must resolve the exposed deployments through the collateral relationship, not a null deployment lookup; overlapping bridge and reserve alerts must not double-count positions. T4 has not been modified or verified here.
- **Missing evidence contract:** real bridge verification needs route identity (source/destination chain IDs and contracts), message/packet identity, payload amount/token/recipient, canonical source transaction or independently verified complete source-log coverage, source/destination block hashes, finality and observation timestamps, independent provider provenance, and pending/verified/mismatch/unavailable states. Global amount totals or route-unspecified nonce inequalities cannot substitute for these observations. No independent verifier is implemented in the current collector.
- **Coverage integration:** T3 provides `Evaluation.issues`, `Evaluation.unavailable_rules`, `Engine.last_evaluation`, `STATUS.data_issues`, and `STATUS.detection_ok`. T3 health/state routes now surface unknown/degraded coverage using `X-Monitoring-Status` and `X-Monitoring-Issues` headers, degraded health and at-least-warning state risk instead of inferring safety from an empty alert list. Shared JSON response schemas are unchanged. No new rule ID silently invokes a financial response for an RPC outage.
- **Status:** local T3 implementation and regression tests; cross-task interface acceptance and real-chain validation pending. Do not treat fixture-mode critical bridge alerts as production evidence.

## CR-006 · T10 environment variables

- **Task:** T10 (branch `t10-sealed-list`)
- **Change:** three lines in `.env.example`: `OPERATOR_PK`, `SAFE_OWNER_PKS`, `SAFE_THRESHOLD=2`. They are read by `sealed/safe.py`, not by `backend/settings.py`. On `local` they fall back to anvil accounts 9 (operator) and 10–12 (owners), using the same public mnemonic as `settings._anvil_key`.
- **Reason:** new roles for the sealed list (`docs/tasks/T10.md`, Keys).
- **Impacted:** T0 (`.env.example`). No change to `backend/settings.py` or `backend/chain.py`.
- **Status:** applied in the T10 pull request; T0 to confirm.
