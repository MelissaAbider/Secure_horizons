---
name: feature-slice
description: Implement the current demo step with the smallest change that passes
---

Build the current step. Reply in English. Do not wait for a plan approval.

1. Read `STATUS.md`. Lock onto `Now`, or the earliest `not started` step.
2. Implement only what that step needs to be observable.
3. Separate in code, not in a long plan: agent proposal, platform check, vault execution, proof. Skip the parts this step does not need.
4. If a non-security choice is missing, pick the smallest option already used in the repo. If none exists, pick the smallest option that runs on Fuji or a local fork and add one `DECISIONS.md` row marked assumed.
5. Add a Check command to the STATUS row and run it.
6. Do not expand into the next step.
