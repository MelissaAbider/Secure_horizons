# Status

Single source of truth for where we are. If this file disagrees with a chat, this file wins.

Rules:

- English only.
- One current task. Do not start a second without parking the first as `blocked` or `done`.
- Update this file at the end of every coding session, in the same change as the work.
- Do not mark a demo step `done` unless the check column command was actually run.
- Do not invent progress. `not started` is a valid state.

## Now

- Phase: T3 surveillance
- Current task: implement the KelpDAO-specific R1–R5 contract in `TASKS.md` section 2.7
- Blocker: T0 fixtures and T1 bridge counters are not yet present in this branch
- Next: implement `backend/rules.py` and tests from fixtures as soon as T0 lands; keep collector integration skipped until T1/T2 land

## Demo path

| Step | Name | Status | Check |
| --- | --- | --- | --- |
| 1 | Connect test Safe on Fuji | not started |  |
| 2 | Aave + Benqi list, sealed | not started |  |
| 3 | Rules separated from instructions | not started |  |
| 4 | Normal move accepted inside list and caps | not started |  |
| 5 | April 2026 incident replay | not started |  |
| 6 | Circuit breaker freezes and pulls back | not started |  |
| 7 | 14% bait blocked after on-chain reread | not started |  |
| 8 | Signed replayable proof, DORA draft not sent | not started |  |

Allowed status values: `not started`, `in progress`, `blocked`, `done`.

## Session log

Newest first. One line. No narrative.

| Date | Who | Did | Left at |
| --- | --- | --- | --- |
| 2026-10-10 | T3 | Replaced generic surveillance rules with KelpDAO bridge-to-Aave causal rules in TASKS | Implementation waiting for T0 fixtures and T1 bridge counters. |
| 2026-10-10 | setup | Moved skills to `.agents/skills` and removed `.devin` | No application code. Stack undecided. |
| 2026-10-10 | setup | Loosened agent loop: build by default, hard-stop only on security | No application code. Stack undecided. |
| 2026-10-10 | setup | Added orient and verify-step skills; one-task loop in AGENTS.md | No application code. Stack undecided. |
| 2026-10-10 | setup | Added English agent context, skills, and this tracker | No application code. Stack undecided. |
