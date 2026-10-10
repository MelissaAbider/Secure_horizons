# Secure Horizons

Delegate daily DeFi treasury management to an AI agent, without giving it the keys.

The agent proposes. The platform verifies. The vault executes.

French source brief: `projet-en-bref.pdf`. English working context: `docs/product/CONTEXT.md`. Where we are: `docs/product/STATUS.md`.

## Agent setup

Share the repo. Do not export a chat.

- `AGENTS.md` — always-on rules for every coding agent
- `.agents/skills/` — shared skills: `orient`, `feature-slice`, `boundary-check`, `measure-honesty`, `verify-step`, `session-close`

Any tool that reads `AGENTS.md` and `.agents/skills/` picks this up on clone. No tool-specific config to copy.

## Before coding

1. Read `docs/product/STATUS.md`, then `CONTEXT.md` and `SCOPE.md`.
2. Decide the open items (language, teller-window key, proof format) in `docs/product/DECISIONS.md`.
3. Freeze thresholds in `docs/product/THRESHOLDS.md` before any measurement run.
4. End every session by updating `STATUS.md`.

## Do not

No key for the agent. No mainnet. No instruction turned into a right. No threshold edited after the tests. No French product docs.
