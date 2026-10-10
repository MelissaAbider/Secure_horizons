---
name: verify-step
description: Run the real check for the current demo step before calling it done
triggers:
  - user
  - model
---

Prove the current step. Reply in English. Do not claim success without a command result.

1. Read `Now` and the matching demo-path row in `docs/product/STATUS.md`.
2. If the Check cell is empty, do not invent a pass. Say which command should be recorded, and stop.
3. Run that command. Paste the exit status and the relevant output.
4. Pass only if the command checks this step's behavior, not a neighboring one.
5. On failure, stop. Do not weaken the test, skip it, or mark the step done.
6. On pass, hand off to `session-close`. The status update happens there, not here.
