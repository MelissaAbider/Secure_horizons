# Status

Single source of truth for where we are. If this file disagrees with a chat, this file wins.

Rules:

- English only.
- One current task. Do not start a second without parking the first as `blocked` or `done`.
- Update this file at the end of every coding session, in the same change as the work.
- Do not mark a demo step `done` unless the check column command was actually run.
- Do not invent progress. `not started` is a valid state.

## Now

- Phase: MVP build, monitoring first (`TASKS.md`). Demo steps 2–4 move to phase 2 (see `DECISIONS.md`).
- Current task: T0 foundations on branch `t0-foundations` (pull request to review); T4 in progress on its own branch
- Blocker: none
- Next: each person picks a task in `TASKS.md` ("Tasks at a glance") and sets its row below to `in progress`

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

## MVP tasks (`TASKS.md`)

One row per task. The check is the task's `make test-tN`, plus its acceptance tests in `TASKS.md`.

| Task | Name | Status | Demo steps covered | Check |
| --- | --- | --- | --- | --- |
| T0 | Repo foundations and shared contract | in progress | all (skeleton) | `make test-t0` |
| T1 | On-chain contracts (local and Fuji) | not started | 1 (simplified vault), 5 | `make test-t1` |
| T2 | Scenario: seed, attack, normal traffic, reset | not started | 5 | `make test-t2` |
| T3 | Monitoring: collector, rules R1–R5, state API | not started | 5, 7 | `make test-t3` |
| T4 | Response and evidence | in progress | 6, 7, 8 | `make test-t4` |
| T5 | Incident and DORA draft | not started | 8 | `make test-t5` |
| T6 | Dashboard | not started | all (screens) | `make test-t6` |
| T7 | Evaluation and metrics | not started | measurement | `make test-t7` |
| T8 | AWS, CI and hosted demo | not started | hosting | `make test-t8` |
| T9 | Jury deliverables | not started | pitch | `make test-t9` |

## Session log

Newest first. One line. No narrative.

| Date | Who | Did | Left at |
| --- | --- | --- | --- |
| 2026-10-10 | T0 | Added repo foundations: shared models, settings, chain helpers, store, fallback stubs, fixture API, fixtures, Makefile, `TASKS.md` | Branch `t0-foundations`, pull request to review |
| 2026-10-10 | setup | Moved skills to `.agents/skills` and removed `.devin` | No application code. Stack undecided. |
| 2026-10-10 | setup | Loosened agent loop: build by default, hard-stop only on security | No application code. Stack undecided. |
| 2026-10-10 | setup | Added orient and verify-step skills; one-task loop in AGENTS.md | No application code. Stack undecided. |
| 2026-10-10 | setup | Added English agent context, skills, and this tracker | No application code. Stack undecided. |
