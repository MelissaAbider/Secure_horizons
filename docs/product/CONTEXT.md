# Secure Horizons — project context

Source: `docs/brief/projet-en-bref.pdf` (Track 1 "Guardians of Value", 10–11 October 2026). The PDF is in French. This file is the English working copy. If they diverge, the PDF wins. Update this file before coding the divergence.

All agent-facing docs, code, commits, UI copy, and proofs are in English. Do not add French product docs.

## One line

The AI agent proposes. The platform verifies. The vault executes.
The sealed list blocks the unknown. The platform stops, in time, what the list still allows: an authorized place that has become dangerous.

## Who it is for

DeFi treasury managers: crypto funds, company or community treasuries, fintechs allocating stablecoins (USDC). They want to delegate 24/7 monitoring to an AI agent without giving it the keys.

## Journey

1. Connect the Safe. Funds stay in the vault. Nothing is custodied by the platform.
2. Pick protocols (Aave, Benqi, others) with checkboxes. The platform turns that into a list of allowed operations, sealed by the signers.
3. Configure the agent: guaranteed rules (caps, human approval, circuit breaker) and free-text strategy instructions.
4. Let it work. The platform watches, cuts, and keeps proof of every decision.

## Two-door vault

- Front door: human signers (example: 3 of 5). Can do anything, including changing the allowed list.
- Teller window: a module attached to the Safe, used by the agent. An operation passes only if it is in the sealed list and within the caps. Otherwise it is refused, with no effect.
- The agent never holds a vault key. The platform signs with a key that can open only the teller window.
- A manipulation changes what the agent wants, not what the vault accepts.

## Sealed list

Each allowed operation is described precisely (contract, function, permitted parameters), then hashed. Hashes are combined into a Merkle root. The vault stores that root. To execute, the caller supplies the operation and the neighboring hashes; the vault recomputes. If it does not land on the seal, the operation is refused.

The list is not secret. Changing it requires the front door.

Illustrative operations, not a frozen list:

- deposit USDC on Aave
- withdraw USDC from Aave
- deposit USDC on Benqi
- withdraw USDC from Benqi

A transfer to an unknown address is not on the list: refused.

## Guaranteed rules vs instructions

Rules are signed through the Safe. No text can modify them.

Brief defaults, until the group freezes them in `docs/product/INVARIANTS.md`:

- allowed protocols: Aave USDC, Benqi USDC
- per-protocol cap: 40%
- max loss per operation: 0.5%
- human approval above $100,000
- automatic circuit breaker enabled

Instructions guide strategy and grant no rights. Brief example: capital preservation first, target 5–7% per year, prefer protocols older than two years, at most three moves per day, never more than 30% on Aave. While "30%" is only an instruction, only the signed 40% cap is guaranteed.

Channels (Telegram, Slack): alerts, questions, pause. Never to widen rights.

Every instruction version is stored with the decisions it produced.

## Authorized does not mean safe

The list does not say whether an allowed protocol is still safe. The work zone is: allowed but dangerous.

Reference incident: Aave, 18 April 2026.

1. Fake collateral: rsETH fraudulently obtained from KelpDAO, massive ETH borrow in under 30 minutes. Aave itself is not hacked; it accepts worthless collateral.
2. Depositor run. The ETH cash reserve is drained. Late depositors are stuck.
3. Displayed yield spikes because the reserve is empty: bait for a yield-chasing agent.
4. rsETH market frozen on 11 chains, including Avalanche, in under 1.5 hours. $8.45B leaves Aave in 48 hours.

"Deposit ETH on Aave" stayed authorized. A price-based loss cap sees nothing: the position still shows a value while it can no longer be withdrawn. The reactive window was 20 minutes to more than one hour.

## What the platform adds

- Watch: liquidity, prices, yield bait proposed by the agent, rule changes, cross-chain contagion.
- React: freeze new deposits and pull back to the vault whatever can still exit. The circuit breaker cannot send funds anywhere else. Only signers reopen.
- Verify before execution: signed rules, facts reread on-chain ("is the market actually open again?"), risk level.
- Prove: every decision, including a refusal, is signed and replayable. Its hash can be anchored. A DORA incident-report draft is ready; a human sends it.

Differentiation: Hypernative, Hexagate, and similar tools start from the protocol and alert. Secure Horizons starts from the manager and their agent: exposure, what can still exit, the agent's next decision. The alert becomes a decision (freeze, exit, how much) and a proof.

## Sunday demo

One story, from alert to proof, on Fuji (Avalanche testnet), with our own test versions of the protocols. The real incident is replayed block by block from public Ethereum data; the live demo reproduces the scenario on the testnet.

1. Connect and configure: Safe, Aave, Benqi, agent.
2. Replay the incident in fast-forward.
3. Circuit breaker: freeze new deposits, pull back what can still exit.
4. Bait: fake "incident resolved, 14%, deposit now" message. The order is on the list, but blocked because the message is false and the reserve is empty.
5. Signed, replayable proof. Incident draft waiting for a human.

Figures to present, measured during the hackathon:

- detection time: minutes from attack start to our alert
- funds still recoverable at alert time, versus management without the platform
- false alerts on normal days

Thresholds are fixed before the tests, and not edited afterward.

Jury weights: detection 30%, response quality 20%, feasibility and technical integration 20%, compliance and explainability 15%, pitch and demo 15%.

## Network and assets

- Demo: Fuji. No mainnet. No real value.
- Asset managers allocate: USDC.
- ETH: Ethereum native asset. rsETH: KelpDAO token representing staked ETH, usable as collateral. The reference incident is about rsETH / ETH, not a hack of Aave's code.

## Out of scope

- Giving a private key or seed to the agent, the platform, or a chat channel.
- Letting an LLM, a tool, or an external message sign, widen the list, change caps, or reopen the circuit breaker.
- Custodying funds on the platform.
- Treating natural-language instructions as a guaranteed rule.
- Inventing a protocol, an incident figure, or a threshold after the tests.
- Building a generic protocol scanner with no link to the manager's position and the agent's next decision.
