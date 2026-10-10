---
name: boundary-check
description: Check that a change respects the vault, the sealed list, and no keys on the agent
---

Boundary check before or after a sensitive change. Reply in English.

Read `docs/product/INVARIANTS.md`. Inspect the diff or the code in question. Answer with a short list:

- who proposes
- who verifies
- who executes
- which key is used, and what it cannot open
- whether free text can change a right
- whether a refusal has a side effect
- whether a secret can leak

Fail if any of these become true: the agent signs, the module changes the list, the circuit breaker sends anywhere but the vault, an instruction becomes a rule, a channel widens a right.

Do not fix a failure by weakening the invariant. Report it.
