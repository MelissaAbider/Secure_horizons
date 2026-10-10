# Decisions

Format: date, decision, why, who. Agents add a row only after a human on the team has decided.

| Date | Decision | Why | Who |
| --- | --- | --- | --- |
| 2026-10-10 | Versioned product context lives in `docs/product/`, translated from `projet-en-bref.pdf`. | Stop agents drifting outside the brief. | initial setup |
| 2026-10-10 | All repo docs, code, commits, and UI copy are English. The French PDF stays the source brief only. | The group codes in English. | initial setup |
| 2026-10-10 | `docs/product/STATUS.md` is the only progress tracker. | A session must be able to resume without the previous chat. | initial setup |
| 2026-10-10 | Agents work one demo step at a time and must update STATUS before stopping. | Keeps coding sessions on the Sunday objective. | initial setup |
| 2026-10-10 | Agents default to building. They stop only for a security or secret hard stop, not for missing non-security details. | A hackathon agent that asks too often does not ship. | initial setup |
| 2026-10-10 | Shared agent files live in `AGENTS.md` and `.agents/skills/`, not in a tool-specific directory. | The whole group does not use the same coding agent. | initial setup |
| 2026-10-10 | MVP is monitoring first: detect, respond, prove, DORA draft. Sealed list, rules vs instructions and the agent's normal move (demo steps 2–4) move to phase 2. | One working end-to-end PoC on one scenario first; detection weighs 30 % of the grid. | team lead |
| 2026-10-10 | Work is split into tasks T0–T9 in `TASKS.md`. Each file has one owning task. The interface contract (`TASKS.md` section 2) is frozen; changes go through `docs/contract-requests.md`. | Four people coding in parallel without merge friction. | team lead |
| 2026-10-10 | Stack: Solidity + Foundry, Python 3.11 + FastAPI (backend, scenario, evaluation), React + Vite + TypeScript (dashboard), AWS us-east-1 (EC2, SNS, S3, Bedrock); anvil locally, Fuji as test network. | Closes the open "language and framework" decision. To confirm in the T0 pull request review. | team lead (proposed in `TASKS.md`) |
| 2026-10-10 | Keys in the MVP: no agent key; the platform's guardian key can only pause deposits and pull funds back to the vault; an owner key stands for the Safe signers on the test network. | Closes the open "teller-window key" decision for the MVP. To confirm in the T0 pull request review. | team lead (proposed in `TASKS.md`) |
| 2026-10-10 | Proofs: each decision is a canonical JSON record in `data/evidence/`, hashed with keccak256 and anchored in `EvidenceRegistry` on Fuji; `make verify` replays it. | Closes the open "where proofs live" decision. To confirm in the T0 pull request review. | team lead (proposed in `TASKS.md`) |
