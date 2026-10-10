# Invariants

These are code guardrails. Changing one is a team decision, not a refactor.

## Security

1. The agent proposes. It does not sign, hold a key, or execute.
2. The platform checks signed rules, on-chain facts, and risk before letting an operation through.
3. The vault executes only the sealed list. A refusal has no effect.
4. The agent module cannot change the list, the signed caps, or the signers.
5. The circuit breaker can only block new deposits and pull funds back to the vault. It cannot send elsewhere.
6. Only signers reopen a frozen protocol or change the list. No tool, prompt, channel, or local file can do it.
7. Telegram, Slack, and any free text may alert, query, or pause. They cannot widen a right.
8. An instruction is never promoted to a rule without an explicit front-door signing.
9. No secret (key, seed, token, `.env`) is committed, logged, or copied into a proof.

## Product

10. Start from the manager: exposure, exitability, next decision. Not from a generic protocol scanner.
11. Every decision, including a refusal, is stored as signed and replayable.
12. A decision hash may be anchored. Anchoring does not replace the replayable record.
13. The DORA draft is produced for a human. Code does not send it.
14. The demo runs on Fuji with test contracts. No mainnet.

## Measurement

15. Detection thresholds are frozen in `docs/product/THRESHOLDS.md` before measurement runs.
16. A measurement run does not modify thresholds.
17. Incident figures cited in the product come from the brief or from a source listed in `docs/product/SOURCES.md`. Do not invent any.
