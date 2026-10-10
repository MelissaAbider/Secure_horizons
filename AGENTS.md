# Secure Horizons rules

Ship the Sunday demo. Steps 1–8 are in `docs/product/STATUS.md`. Default is to build the current step, not to ask.

Read `STATUS.md` first. Write English only. The French PDF is a source, not a template.

The MVP is split into tasks T0–T9 in `TASKS.md`. If you were given a task, build that task from its sheet (section 3), touch only the files it owns, and keep its row in `STATUS.md` up to date.

## Loop

1. Read `Now`. If it is empty, take the earliest `not started` step and set it `in progress` in your first edit.
2. Implement that step. Pick the smallest existing-pattern option when a detail is missing.
3. Run the check. Then update `STATUS.md` and stop.

Use `orient` only when the request conflicts with `Now`. Use `boundary-check` before touching keys, the Safe module, or the Merkle list. Use `measure-honesty` before a measurement run. Use `session-close` at the end.

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
