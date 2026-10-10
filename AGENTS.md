# Secure Horizons rules

Ship the Sunday demo. Steps 1–8 are in `docs/product/STATUS.md`. Default is to build the current step, not to ask.

Read `STATUS.md` first. Write English only. The French PDF is a source, not a template.

The MVP is split into tasks T0–T9 in `TASKS.md`. If you were given a task, build that task from its sheet (section 3), touch only the files it owns, and keep its row in `STATUS.md` up to date.

## Loop

1. Read `Now`. If it is empty, take the earliest `not started` step and set it `in progress` in your first edit.
2. Implement that step. Pick the smallest existing-pattern option when a detail is missing.
3. Run the check. Then update `STATUS.md` and stop.

Use `orient` only when the request conflicts with `Now`. Use `boundary-check` before touching keys, the Safe module, or the Merkle list. Use `measure-honesty` before a measurement run. Use `session-close` at the end.

## Before every push

- Update `docs/product/STATUS.md` and report progress to the user before running `git push`.
- State what is implemented, which checks actually passed or failed, what remains incomplete or blocked, and the branch and commits to be pushed.
- Distinguish synthetic-fixture validation from live-chain verification. Do not describe passing unit tests as proof that the whole task is complete.
- Push only when explicitly requested; a progress report does not grant permission to push.
- Publish Melissa's T3 work only to `feature/t3-kelpdao-surveillance`. Never push directly to `main` or `master`; verify the current branch and use an explicit destination ref.

## T3 verification

- Run `python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.pytest_cache/t3-validation` from the repo root. The workspace-local temporary directory avoids the Windows system-temp permission failure.
- Version-3 T3 behavior and evidence limitations are in `docs/product/THRESHOLDS.md`; CR-004 tracks the unapproved cross-task integration delta. Do not rewrite other tasks or their fixtures to match T3 results.
- T3 collection: `python -m backend.collector --once [--block N]`; monitoring: `python -m backend.engine --loop`. These are the equivalents of `make monitor-once [BLOCK=N]` and `make monitor` when GNU make is unavailable.
- T3 live smoke is read-only and opt-in with `T3_LIVE=1`; it requires a configured RPC and deployed/seeded contracts. A skipped live check is not evidence of a successful deployment test.

## Speed

- Act. Do not present a plan unless the user asked for one, or a hard stop applies.
- One step at a time. A helper needed by that step is in scope. A second demo step is not.
- Missing stack: use what the repo already has. If the repo is empty, use the least tooling that runs the step on Fuji or a local fork, and record the choice in `DECISIONS.md` as "assumed, reversible".
- Missing copy, names, or file layout: follow neighbors. Do not ask.
- Reread a file before editing it. Smallest diff that makes the step pass.
- No drive-by refactor.

## Hard stops

Stop only for these. Say the blocker in one line and continue everything else.

- A change would give the agent a key, widen the sealed list, send funds outside the vault, or let free text change a right.
- A frozen threshold would be edited.
- A mainnet transaction, a real secret, or a committed `.env`.
- The user explicitly asked to wait.

Do not stop for style, naming, optional abstractions, or an undecided non-security detail.
