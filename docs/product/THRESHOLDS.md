# T3 KelpDAO detection contract — version 3

Status: DEVELOPMENT POLICY, NOT FROZEN FOR EVALUATION OR VALIDATED ON HISTORICAL CHAIN DATA.

Scope: T3 rules and ingestion only. Executable policy: `backend/config/rules.yaml`; regression specifications: `backend/tests/test_t3_rules.py`, `test_t3_hardening.py`, and `test_t3_engine.py`. This supersedes the version-2 T3 detection behavior on this branch. Shared models, T1 contracts, T2 scenarios, T4 response logic, and historical fixtures are unchanged by this hardening. Integration changes are tracked in CR-004 in `docs/contract-requests.md`.

## Rules

| Rule | Exact condition and severity | Evidence boundary |
| --- | --- | --- |
| R1_BRIDGE_INVARIANT | Released counter exceeds source counter OR destination nonce exceeds source nonce. `critical` only for explicitly synthetic `source="fixture"` data; otherwise `warning` with `evidence_status="unverified"`. | Counters are NOT independent proof of a missing canonical source message. Live and historical replay inputs lack route, message identity, finalized source coverage and independent source verification. Missing counters produce an explicit coverage issue, not a healthy result. No promotion based on price/backing_ratio_bps. |
| R2_COLLATERAL_SURGE | rsETH collateral increases >=50% above the minimum prior collateral in the bounded window. Uncorroborated increases remain `warning`, even >=200%. Concurrent synthetic R1 anomaly permits `high` at >=50% and `critical` at >=200%. Zero baseline to positive amount is a warning (high with synthetic correlation), without an invented percentage. | Only deployments containing a treasury position and accepting/holding the collateral. At least two prior samples. Current sample excluded. Correlation is not fund provenance and no live critical bridge correlation is currently available. Minimum baseline retains cumulative increases until it ages out; deposit recovery can still cause a warning. |
| R3_LIQUIDITY_DRAIN | Available-liquidity drop >=30% / >=60% from the maximum prior value gives `high` / `critical`. Additionally borrowed/supplied >=90% / >=98% gives `warning` / `critical`; zero available liquidity gives `critical`. Emit the highest severity for that reserve. | Persistent utilization and zero-liquidity checks work without history and after a slow drain ages out of the window. Compute utilization from integer amounts, not the rounded display field. Liquidity risk is not proof of fraud. |
| R4_EXITABILITY_DROP | Effective amount = 0 if the position's reserve is paused; otherwise min(position supplied, reported withdrawable amount, reserve liquidity). Effective/supplied <80% / <50% gives `high` / `critical`. | Exact integer cross-multiplication decides thresholds, even one base unit below a boundary. Displayed basis points do not decide. A freeze alone does not block withdrawals in the MiniLend model. This remains an upper-bound estimate, not an execution simulation or guarantee. |
| R5_CONTAINMENT | A currently frozen/paused exposed reserve, or a paused bridge whose collateral connects to exposed deployments, gives `high`; `critical` if any concerned position has exact effective exitability <50%. | Evaluated at startup and on every sample, not only a transition. Bridge alerts are global (`deployment_id=null`), reserve alerts deployment-scoped. A bridge pause does not itself imply that lending withdrawals are blocked. |

Amounts used in comparisons are integers in base units. Percentages and dollar values are presentation only. The window holds **20 samples including the current sample**, so there are at most 19 prior samples. Thresholds 50/200, 30/60, 80/50 and 90/98 are development risk policies, not incident-derived guarantees. Do not optimize them to reproduce a fixed alert count.

## Coverage and validity

- `evaluate_snapshot` returns alerts **and** coverage issues/unavailable rules. `evaluate_all` is the list-only compatibility wrapper, not a detector-health interface.
- The engine retains the report as `last_evaluation`; `STATUS.data_issues` and `STATUS.detection_ok` expose incomplete coverage internally. RPC connectivity alone does not mean detection is healthy. Public live health/state routes are still pending.
- Invalid amounts, negative/non-finite valuations, duplicate identities, missing token/reserve references, mixed-chain windows, backwards timestamps, and unexpected reserve-inventory changes are rejected.
- An unavailable rule does not clear its existing alert latch. Continued bad state is deduplicated, escalation is emitted, and genuine recovery allows a new alert.
- Live input age >60 seconds or future skew >5 seconds is rejected. These are configurable operational limits, not a claim about KelpDAO's reaction window. Historical fixtures bypass wall-clock age checks; the live loop rejects fixture data.
- Same-height conflicting snapshots are rejected; lagging RPC heads are not treated as canonical chain resets. The schema lacks block hashes, so full reorg detection is NOT implemented.
- Serialized handlers run separately from collection. Queue capacity is 128; saturation applies explicit backpressure rather than silently dropping alerts. A hung handler can still stall dispatch; this is not a durable queue.
- Store write failures do not consume the detection latch. The shared store does not provide transactional snapshot+alert writes or durable exactly-once dispatch; retries can duplicate stored entries. Consumers must deduplicate stable alert IDs.
- RPC fallback occurs after three failed polls; primary probes run every 30 fallback polls. Exception details and credential-bearing RPC URLs are not logged by T3.

## Verified versus not verified

Regression tests cover synthetic evidence, missing evidence, legitimate large inflows, slow drains, exact boundaries, pause/freeze behavior, deduplication, invalid snapshots, clock freshness, maintenance, handler isolation, persistence retry and mocked RPC behavior.

Re-evaluating the unchanged attack snapshots now yields **eight alerts**: the previous seven plus the previously missed global bridge-pause alert. Normal snapshots yield zero. Historical `alerts.json`/decision records remain version-2 examples; they are not regenerated or presented as version-3 evidence.

No historical incident transactions, independent cross-chain evidence, real RPC latency, false-positive rate on representative traffic, or live contract withdrawals have been verified. There is no guarantee of detecting every variant or recovering funds before liquidity disappears.

## Evaluation protocol

- Freeze configuration bytes and detector revision before held-out measurements; retain their hashes and dataset identifiers.
- Attack start must come from independently labeled destination execution of the forged message, not an alert or a threshold crossing.
- Report detection latency from that event to alert receipt, plus monitoring gaps and end-to-end response latency separately.
- Evaluate legitimate bridge transfers, large deposits/withdrawals, maintenance, slow drains, stale providers, source finality delays and RPC disagreement. Include misses, benign warnings and high/critical false positives.
- Do not report these unit-test fixtures as measured real-incident detection accuracy.
