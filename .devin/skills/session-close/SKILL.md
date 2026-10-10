---
name: session-close
description: Close the session by updating STATUS so the next agent can resume without the chat
triggers:
  - user
  - model
---

The next agent has no chat history. Leave `docs/product/STATUS.md` able to resume alone. Reply in English. Be brief. Do not add follow-up tasks.

1. State the step number and the new status: `in progress`, `blocked`, or `done`.
2. `done` only if `verify-step` ran the Check command and it passed. Otherwise use `in progress` or `blocked`.
3. Update `Now` so current task, blocker, and next are each one line.
4. Update that demo-path row, including the Check command if one now exists.
5. Prepend one session-log row: date, who, did, left at. No narrative.
6. Confirm the diff has no secret, key, or real `.env`.
7. Add a `DECISIONS.md` row only if a human decided. Do not record your own guess.
8. Stop. Do not start the next step.
