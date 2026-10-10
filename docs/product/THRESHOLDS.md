# Detection thresholds

Status: NOT FROZEN.

MVP: the thresholds in use are the five rules R1–R5 of `TASKS.md` 2.7, stored in `backend/config/rules.yaml` (owned by T3). Freezing them means recording the sha256 of that file in this section, and anchoring it on Fuji (T7), before the first measurement run.

Do not start a measurement run, and do not announce a detection number, until this section is filled and marked FROZEN. After that, do not edit the values. A new threshold set is a new dated file, not an in-place edit.

## Freeze before tests

| Signal | Threshold | Unit | Why this threshold |
| --- | --- | --- | --- |
| Withdrawable liquidity / position |  | % |  |
| Abnormal displayed-yield jump |  | % or std dev |  |
| Gap between displayed value and withdrawable value |  | % |  |
| Cross-chain contagion (freeze or incident on another chain of the same market) |  | bool / delay |  |
| Max age of an accepted on-chain fact |  | blocks or seconds |  |

## Forbidden after freeze

- Tune a threshold because a run missed or over-alerted.
- Change the definition of "attack start" after measuring detection time.
- Compare against unmanaged treasury with a different definition of "still recoverable".

## Measurement definitions

- Attack start: first replayed block where the fake collateral is used. Confirm against the source before freezing.
- Detection time: from that block to the platform alert.
- Still recoverable: share of the position a withdrawal to the vault could still exit at the alert block.
- False alert: an alert on a normal day, with no injected incident.
