# Integration and phase 2

> Light version of `TASKS.md` (full detail there). Same numbering, so a reference like "2.7" means the same thing in both.

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
