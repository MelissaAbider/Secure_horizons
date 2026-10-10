---
name: orient
description: Resume the current demo step and start it unless a hard stop applies
---

Get back on the demo, then build. Reply in English.

1. Read `docs/product/STATUS.md` only.
2. If `Now` has a task, that is the task. State the next concrete action in one sentence and do it.
3. If `Now` is empty, take the earliest `not started` step. Set it `in progress` in the first edit. Then build.
4. If the user asked for a different step while one is `in progress`, finish the current step's smallest passing slice first, unless they explicitly said to switch. On an explicit switch, park the current step as `in progress` and start the requested one.
5. If the request is outside steps 1–8, do the part that serves the current step and skip the rest. Mention the skip in one line. Do not lecture.
6. Hard stop only if the work needs a key for the agent, a list change without signers, funds leaving the vault, a frozen-threshold edit, mainnet, or a real secret.
