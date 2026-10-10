# T3 KelpDAO detection contract — version 4

Status: DEVELOPMENT POLICY, NOT FROZEN FOR EVALUATION OR VALIDATED ON HISTORICAL CHAIN DATA.

Version 4 (KelpDAO deep review) changes versus version 3: live bridge mismatch is `critical` when treasury is exposed to that collateral (`high` otherwise) instead of `warning`; R1 is sticky and never clears on counter recovery; R2 correlation uses any bridge anomaly in the window (live or fixture) rather than the current sample only; R3 adds a lower drain threshold (10%) once a bridge anomaly exists in the window. Rationale: in the real incident the forged release was the root cause and the whole drain happened within the hour; waiting for forensic proof before escalating would have cost the reaction window.

Scope: T3 read-only collection, rules, ingestion and state API. Executable policy: `backend/config/rules.yaml`; regression specifications: `backend/tests/test_t3_rules.py`, `test_t3_hardening.py`, `test_t3_engine.py`, `test_t3_collector.py`, and `test_t3_api.py`. This supersedes the version-2 T3 detection behavior on this branch. Shared models, T1 contracts, T2 scenarios, T4 response logic, and historical fixtures are unchanged by this hardening. Integration changes are tracked in CR-004 in `docs/contract-requests.md`.

## Rules

| Rule | Exact condition and severity | Evidence boundary |
| --- | --- | --- |
| R1_BRIDGE_INVARIANT | Released counter exceeds source counter OR destination nonce exceeds source nonce. `critical` when any exposed deployment accepts or holds this collateral, `high` otherwise, regardless of source. `evidence_status` is `synthetic` for fixtures and `unverified` for live data. The alert is sticky: once latched it stays active until a monitor reset by signers (store generation change), even if counters later look consistent. | Counters are NOT independent proof of a missing canonical source message; the alert says so. The escalation is justified by the KelpDAO timeline (forged release to drained liquidity in under one hour): an exposed treasury cannot wait for forensic confirmation. Missing counters produce a coverage issue, not a healthy result. No promotion based on price/backing_ratio_bps. |
| R2_COLLATERAL_SURGE | rsETH collateral increases >=50% above the minimum prior collateral in the bounded window. Uncorroborated increases remain `warning`, even >=200%. If any snapshot in the window shows a bridge anomaly (live or fixture), `high` at >=50% and `critical` at >=200%. Zero baseline to positive amount is a warning (high with correlation). | Only deployments containing a treasury position and accepting/holding the collateral. At least two prior samples. Current sample excluded. Correlation is pattern-based (release then deposit), not per-wallet provenance. Minimum baseline retains cumulative increases until it ages out; deposit recovery can still cause a warning. |
| R3_LIQUIDITY_DRAIN | Available-liquidity drop >=30% / >=60% from the maximum prior value gives `high` / `critical`. With a bridge anomaly in the window, a drop >=10% already gives `high`. Additionally borrowed/supplied >=90% / >=98% gives `warning` / `critical`; zero available liquidity gives `critical`. Emit the highest severity per reserve. | The lowered post-anomaly threshold catches the first borrow tranches against stolen collateral (on fixtures: block 818 instead of 826, 4 samples earlier). Persistent utilization and zero-liquidity checks work without history and after a slow drain ages out of the window. Liquidity risk alone is not proof of fraud. |
| R4_EXITABILITY_DROP | Effective amount = 0 if the position's reserve is paused; otherwise min(position supplied, reported withdrawable amount, reserve liquidity). Effective/supplied <80% / <50% gives `high` / `critical`. | Exact integer cross-multiplication decides thresholds, even one base unit below a boundary. Displayed basis points do not decide. A freeze alone does not block withdrawals in the MiniLend model. This remains an upper-bound estimate, not an execution simulation or guarantee. |
| R5_CONTAINMENT | A currently frozen/paused exposed reserve, or a paused bridge whose collateral connects to exposed deployments, gives `high`; `critical` if any concerned position has exact effective exitability <50%. | Evaluated at startup and on every sample, not only a transition. Bridge alerts are global (`deployment_id=null`), reserve alerts deployment-scoped. A bridge pause does not itself imply that lending withdrawals are blocked. |

Amounts used in comparisons are integers in base units. Percentages and dollar values are presentation only. The window holds **20 samples including the current sample**, so there are at most 19 prior samples. Thresholds 50/200, 30/60/10, 80/50 and 90/98 are development risk policies, not incident-derived guarantees. Do not optimize them to reproduce a fixed alert count.

## Mapping to the KelpDAO incident

| Incident phase (SOURCES.md) | Rule | Why it fits |
| --- | --- | --- |
| Forged LayerZero message releases ~116,500 rsETH with no source burn | R1 | Direct invariant on the bridge: released > locked, destination nonce ahead of source. Critical for an exposed treasury. |
| Stolen rsETH deposited as collateral on lending markets within minutes | R2 | Collateral jump correlated with the bridge anomaly in the window; the correlation is what separates it from a legitimate large deposit. |
| WETH borrowed against it in tranches, liquidity drained in under an hour | R3 | Low post-anomaly drain threshold plus utilization pressure; persistent even when the drain is slow. |
| Treasury can no longer withdraw its full position | R4 | Exact exitability from on-chain amounts; paused market means zero. |
| Kelp pauses the bridge; Aave freezes rsETH markets | R5 | Observed on-chain containment, active-state not transition, bridge-scope and reserve-scope. |

Known residual gaps, deliberately not hidden: no canonical source-chain proof of the forged message; no per-wallet provenance of the deposited collateral; thresholds are untested on representative traffic; a reserve `frozen` flag does not reduce exitability in the MiniLend model.

## Coverage and validity

- `evaluate_snapshot` returns alerts **and** coverage issues/unavailable rules. `evaluate_all` is the list-only compatibility wrapper, not a detector-health interface.
- The engine retains the report as `last_evaluation`; `STATUS.data_issues` and `STATUS.detection_ok` expose incomplete coverage internally. RPC connectivity alone does not mean detection is healthy. `/api/health` and `/api/state` expose coverage issues through the ASCII JSON `X-Monitoring-Issues` header and `X-Monitoring-Status=degraded`. Health is degraded for missing, invalid or stale data, an inactive/unhealthy engine, handler failures or queue backpressure. State risk is at least warning for unknown coverage, without fabricating a critical fraud alert. Shared response schemas are unchanged.
- The collector pins every contract read to the requested block and rechecks its hash at the end. A changed block, incomplete MiniLend inventory, inconsistent liquidity accounting or RPC failure prevents returning a partial snapshot. Oracle `no price` returns zero with an explicit coverage issue. Absent optional bridge ABI functions remain null, never reconstructed as canonical evidence.
- Collection assumes the configured MiniLend interface and asset inventory, not arbitrary production lending contracts. Paused reserves report zero estimated withdrawals; frozen reserves can still be withdrawn. Token decimals are cached by chain/deployment/vault/address and committed to cache only after a valid snapshot.
- API risk uses the current engine window boundary after maintenance/reset, not historical alert severity. Series are chronological; alerts are newest first and deduplicated by ID; idle funds do not count as exposed losses. `USE_FIXTURES` is checked per request.
- Independent historical-chain forensic proof is not a prerequisite for delivering this MVP collector/API. Live counter anomalies retain version-3 unverified semantics; no claim of real-world proof is made.
- Invalid amounts, negative/non-finite valuations, duplicate identities, missing token/reserve references, mixed-chain windows, backwards timestamps, and unexpected reserve-inventory changes are rejected.
- An unavailable rule does not clear its existing alert latch. Continued bad state is deduplicated, escalation is emitted, and genuine recovery allows a new alert. R1 is additionally sticky: a return to consistent counters does not clear it, and a coverage issue records that the earlier anomaly remains latched.
- Live input age >60 seconds or future skew >5 seconds is rejected. These are configurable operational limits, not a claim about KelpDAO's reaction window. Historical fixtures bypass wall-clock age checks; the live loop rejects fixture data.
- Same-height conflicting snapshots are rejected; lagging RPC heads are not treated as canonical chain resets. The schema lacks block hashes, so full reorg detection is NOT implemented.
- Serialized handlers run separately from collection. Queue capacity is 128; saturation applies explicit backpressure rather than silently dropping alerts. A hung handler can still stall dispatch; this is not a durable queue.
- Store write failures do not consume the detection latch. The shared store does not provide transactional snapshot+alert writes or durable exactly-once dispatch; retries can duplicate stored entries. Consumers must deduplicate stable alert IDs.
- RPC fallback occurs after three failed polls; primary probes run every 30 fallback polls. Exception details and credential-bearing RPC URLs are not logged by T3.

## Verified versus not verified

Regression tests cover synthetic evidence, missing evidence, legitimate large inflows, slow drains, exact boundaries, pause/freeze behavior, deduplication, invalid snapshots, clock freshness, maintenance, handler isolation, persistence retry and mocked RPC behavior.

Re-evaluating the unchanged attack snapshots yields **eight alerts**, with the first liquidity alert now at block 45201818 (was 45201826). Normal snapshots yield zero. Review-specific tests live in `backend/tests/test_t3_kelpdao_review.py`. Historical `alerts.json`/decision records remain version-2 examples; they are not regenerated or presented as version-3 evidence.

No historical incident transactions, independent cross-chain evidence, real RPC latency, false-positive rate on representative traffic, or live contract withdrawals have been verified. There is no guarantee of detecting every variant or recovering funds before liquidity disappears.

## Evaluation protocol

- Freeze configuration bytes and detector revision before held-out measurements; retain their hashes and dataset identifiers.
- Attack start must come from independently labeled destination execution of the forged message, not an alert or a threshold crossing.
- Report detection latency from that event to alert receipt, plus monitoring gaps and end-to-end response latency separately.
- Evaluate legitimate bridge transfers, large deposits/withdrawals, maintenance, slow drains, stale providers, source finality delays and RPC disagreement. Include misses, benign warnings and high/critical false positives.
- Do not report these unit-test fixtures as measured real-incident detection accuracy.
