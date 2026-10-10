# KelpDAO detection thresholds

Status: SPECIFIED, NOT YET FROZEN BY A MEASUREMENT RUN.

These values are the implementation contract in `TASKS.md` section 2.7. Freeze them before the first evaluation run. After freeze, a new threshold set requires a new dated file.

| Rule | Signal | High | Critical | Reason |
| --- | --- | --- | --- | --- |
| R1 bridge invariant | destination released minus canonical source locked; destination/source nonce order | — | gap > 0 or destination nonce > source nonce | A valid bridge route must conserve value and preserve canonical message order. Any confirmed mismatch is a security failure, not normal volatility. |
| R2 collateral surge | rsETH collateral increase against max of previous 20 snapshots | >= 50% | >= 200% | Detects rapid propagation of bridge-released rsETH into lending collateral. Current snapshot is excluded from baseline. |
| R3 liquidity drain | available liquidity decrease against max of previous 20 snapshots | >= 30% | >= 60% | Detects extraction of borrowable assets such as WETH. Current snapshot is excluded from baseline. |
| R4 exitability drop | withdrawable amount / supplied position | < 80% | < 50% | Measures the treasury's actual ability to leave, independent of displayed price. |
| R5 containment | bridge pause or exposed reserve freeze/pause transition | transition | transition while a concerned position is < 50% withdrawable | On-chain containment confirms the incident; external text alone never triggers it. |

## Evaluation rules

- Normal fixtures must produce zero alerts.
- Attack fixtures must produce the seven alerts specified in T3-10.
- Do not tune values after seeing evaluation results.
- Do not treat `backing_ratio_bps` as R1. It remains display-only compatibility data.
- Do not use a price drop or APY spike as a proxy for this attack: neither is the root invariant.

## Measurement definitions

- Attack start: first destination block accepting a bridge release with no canonical source lock/burn and/or a destination nonce ahead of the source nonce.
- Detection time: from attack-start block to the first critical alert.
- Still recoverable: share of the treasury position a withdrawal to the vault could still exit at the alert block.
- False alert: a high or critical alert on a normal run with no injected bridge mismatch.
