# External datasets for T3 detection and ML

All files here are downloaded or extracted from public sources with the scripts in `evaluation/data_sources/`.
Nothing in this folder is committed (see `.gitignore`); re-run the scripts to rebuild.

## kelpdao/ — real Aave V3 Ethereum and rsETH bridge data (SQD Portal, no API key)

| File pattern | Content | Label |
| --- | --- | --- |
| `aave_events_kelpdao_attack_24907500_24909500.jsonl` | 9,245 decoded Aave Pool events over 2,000 blocks around the forged release (block 24,908,285) | **attack** |
| `aave_events_normal_w1..w5_*.jsonl` | 5 windows of 2,000 blocks each, weeks before the incident, ~17,000 events | **normal** |
| `bridge_ethereum_*.jsonl` | `OFTReceived` on the Kelp bridge adapter: every rsETH delivery to Ethereum with its LayerZero GUID | bridge destination side |
| `bridge_unichain_*.jsonl` | `OFTSent` on the rsETH OApp: every send from Unichain with GUID (to reconcile against deliveries) | bridge source side |

Event rows: `block, timestamp, tx, log_index, event, reserve, asset, user, amount, ...`. Amounts are base-unit strings.
Events: `supply`, `withdraw`, `borrow`, `repay`, `reserve_update` (rates and indexes), `collateral_enabled`, `liquidation`.

Observed in the attack window (block offset from 24,908,285): rsETH collateral supplied at +16 (1), +25 (5,000), +31 (20,000),
+37 (27,999); WETH borrowed at +28 (4,924), +34 (19,745), +40 (27,771); WETH withdrawals 5,594 before vs 340,006 after.

Rebuild: `python -m evaluation.data_sources.sqd_aave_events --from F --to T --label L` and
`python -m evaluation.data_sources.sqd_bridge_events --chain ethereum|unichain --from F --to T`.

## incidents/ and ml/ — multi-incident labeled dataset (FROZEN for the first ML iteration)

`evaluation/data_sources/incidents.json` lists 15 real incidents (bridge and lending, EVM chains indexed by SQD).
`sqd_incident_logs.py` pulled every log of the victim contracts over a 3,000-block attack window and five 3,000-block
normal windows per incident. `build_ml_dataset.py` decodes known lending/bridge events, aggregates per block, slides a
20-sample window (10-block step) and labels windows overlapping [attack_block, attack_block + 600].

Result (`ml/windows.csv`, `ml/dataset_card.json`): **11,675 windows, 597 positive, 12 incidents with decodable events**.
Rich positives: KelpDAO, Nomad, Ronin, Multichain, Euler, Cream, Radiant, UwuLend. Thin: Harmony, Poly, Hundred.
Sonne has 0 positive windows (victim contract listed is the comptroller; flows live on the cTokens — kept as a known gap).
Orbit, BonqDAO, Beanstalk produced too few decodable events to yield windows.

Features are chain- and token-agnostic (log10 base-unit amounts, counts, ratios, actor concentration, outflow acceleration,
max single amount vs normal-window baseline). No USD, no oracle dependency.

Decision: stop collecting here. Train on this set plus T2 synthetic variants; hold out KelpDAO as the primary test.

### ml/train/ — cleaned, leakage-free training material (`prepare_training_set.py`)

| File | Content |
| --- | --- |
| `train.csv` | 3,406 windows, **328 positive**, 7 incidents (Cream, Euler, Multichain, Nomad, Radiant, Ronin, UwuLend) |
| `test.csv` | 1,683 windows, **80 positive**, KelpDAO only — never used for training or model selection |
| `folds.json` | 5 leave-one-incident-out folds (Cream, Euler, Multichain, Nomad, Ronin). Radiant and UwuLend are train-only: too thin to validate alone |
| `features.json` | 19 features, label, group column (`incident`), per-feature train statistics |
| `integrity_report.json` | every cleaning step with counts |

Cleaning applied: incidents with < 30 positives or < 100 negatives dropped (Harmony, Hundred, Poly, Sonne); windows with
< 3 active blocks dropped; identical feature vectors within one file deduplicated (short attacks like Radiant collapse from 65
to 15 distinct positives — the earlier count was sliding-window repetition, not information); non-finite values clipped;
`out_in_ratio` replaced by a bounded log ratio. Train/test and fold disjointness are asserted by incident.

Rules for using it: group every split by `incident`; report per-fold metrics, not a pooled score; KelpDAO result is the
only number that speaks to the target scenario; do not tune on test.

## xchainwatcher/ — Ronin and Nomad bridge datasets (MIT, ~2.2 GB)

Raw transaction receipts, block tables and token prices for both bridges, before / during / after the attacks, plus
`ronin-bridge/decoded_data/decoded_txs_aggregated.csv`. Source: https://github.com/AndreAugusto11/XChainWatcher
(`gdown 1YeBQpXWUB8LEXkbzyF0uJqOfhxqKiby7 --folder`). Use to test bridge-invariant logic on two real attacks.

## defihacklabs/ — index of bridge incidents

`bridge_incidents.json`: 20 bridge-related incidents (2021–2026) with tx hashes when published and the PoC path in
DeFiHackLabs. Rebuild: `python -m evaluation.data_sources.defihacklabs_index`. Fork blocks are inside each PoC file.

## Not collected (requires a paid/keyed archive RPC)

Point-in-time reserve state (`getReserveData` at historical blocks). The event streams above allow rebuilding
supplied/borrowed/available per asset by cumulating flows from a known starting state; `reserve_update` events give
rates and indexes at each change.
