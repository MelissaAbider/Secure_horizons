# Context

> Light version of `TASKS.md` (full detail there). Same numbering, so a reference like "2.7" means the same thing in both.

## 1.1 What we are building

A **DeFi treasury monitoring** platform. Our client is a fund manager who places the funds of their vault (a Safe) in lending protocols. The platform:

1. reads, at every block, the state of the markets where the vault has money and the state of its positions;
2. computes **a few simple indicators** (withdrawable share, utilization, liquidity, collateral backing);
3. raises **explainable alerts** (one sentence with numbers per alert);
4. **reacts** automatically by tightening: pause new deposits, emergency withdrawal to the vault of whatever is still withdrawable;
5. **proves**: every decision is recorded, hashed and its hash anchored on Avalanche Fuji; a `verify` command lets an auditor replay it;
6. opens an **incident** and prepares the pre-filled **DORA report**, which a human validates and sends;
7. shows everything in a **dashboard**.

**Out of MVP (phase 2, do not build now)**: the AI agent proposing allocations, the choice of instructions and of the allowlist, signed mandates, inter-agent security, advanced detection rules (see section 5).

## 1.2 The single scenario (common thread of the demo and the tests)

Synthetic replay of the Kelp/Aave incident of April 18, 2026, **on our own contracts deployed on Fuji** (and on a local anvil chain for tests).

| Phase | What happens on-chain | What the platform must do |
|---|---|---|
| 0. Normal | Bots supply and borrow. The vault has 150 WETH + 400,000 USDC on `lend-eth`, 100 WETH + 300,000 USDC on `lend-avax`. | Nothing (no alert ≥ high). |
| 1. Forged mint | The bridge mints 5,000 rsETH **with no backing**: rsETH backing drops from 100% to ~19%. | **R1 critical** in the next block → pause deposits + emergency withdrawal of all our positions in the deployments that accept rsETH as collateral + incident opened. |
| 2. Fake collateral | The attacker deposits the rsETH as collateral on `lend-eth`. | (already safe) |
| 3. Draining | The attacker borrows the WETH in chunks until none is left. | R2 / R3 if we are still exposed. |
| 4. Rush | Bots try to withdraw their WETH; the last ones stay stuck. | R4 if one of our positions is stuck. |
| 5. Late freeze | The protocol guardian freezes the rsETH reserve. | R5 (context information). |

**The number we want to show**: our withdrawal happens while 100% of the position is still withdrawable, whereas a passive supplier stays stuck.

## 1.3 Architecture

```
            ┌───────────────────────── Avalanche Fuji (or anvil locally) ──────────────────────────┐
            │  MockERC20 (USDC, WETH)   RsETH + MockBridge   MockOracle                             │
            │  MiniLend "lend-eth"      MiniLend "lend-avax"                                        │
            │  TreasuryVault (the vault)                     EvidenceRegistry (hashes)              │
            └───────▲───────────────────────────────▲───────────────────────────────▲──────────────┘
                    │ scripts (T2)                   │ read at every block            │ guardian tx / anchoring
        ┌───────────┴─────────┐          ┌──────────┴──────────────────────────────┴────────────┐
        │ scenario/ (T2)      │          │ backend/ (FastAPI, single process)                     │
        │ seed, attack,       │          │  collector → Snapshot → engine (rules R1..R5) → Alert  │
        │ normal, reset       │          │  → responder (matrix) → Decision → executor (tx)       │
        └─────────────────────┘          │  → evidence (hash, anchoring, verify)                  │
                                         │  → incidents + DORA (report, optional Bedrock)         │
                                         │  API /api/* (T3, T4, T5, T2, T7)                       │
                                         └──────────────▲──────────────────────────▲─────────────┘
                                                        │ HTTP (polling 2 s)       │ SNS, S3, Bedrock
                                         ┌──────────────┴──────────┐      ┌────────┴─────────┐
                                         │ frontend/ (T6) Vite     │      │ AWS (T8)         │
                                         └─────────────────────────┘      └──────────────────┘
            evaluation/ (T7): runs scenarios, reads the API, computes metrics → data/eval/
```

## 1.4 Stack

| Component | Choice |
|---|---|
| Contracts | Solidity 0.8.24, Foundry (`forge`, `anvil`), OpenZeppelin |
| Backend, scenario, evaluation | Python 3.11, FastAPI, Pydantic v2, web3.py ≥ 6.20, PyYAML, boto3, pytest |
| Frontend | Node 20, Vite, React 18, TypeScript, Tailwind, Recharts, Vitest |
| Chain | `local` = anvil (chainId 31337, instant blocks); `fuji` = Avalanche Fuji C-Chain (chainId 43113, ~2 s per block, explorer `https://testnet.snowtrace.io`) |
| Cloud | AWS us-east-1 only: EC2, SNS, S3, Bedrock (Claude models), SSM Parameter Store |

## 1.5 Repo tree and owner of each folder

Each file has **a single owning task**. You only modify your task's files.

```
.
├── TASKS.md                     T0 (this document)
├── CLAUDE.md                    T0 (rules for every Claude Code)
├── README.md                    T9 (final version; each task provides its paragraph in its PR)
├── Makefile                     T0 (includes mk/*.mk; each task has its mk/tN.mk)
├── mk/tN.mk                     TN (make targets of task N)
├── .env.example .gitignore .pre-commit-config.yaml requirements.txt   T0
├── contracts/                   T1 (Foundry project: src/, script/, test/)
├── deployments/<network>.json   T1 (written by the deploy script, committed for fuji)
├── abi/<Contrat>.json           T1 (exported by make abi)
├── scenario/                    T2 (except scenario/__init__.py, created by T0)
├── backend/
│   ├── __init__.py main.py models.py settings.py chain.py store.py fixtures.py   T0 (frozen)
│   ├── collector.py engine.py rules.py config/rules.yaml api/state.py            T3
│   ├── responder.py executor.py notify.py evidence.py cli.py
│   │   config/playbook.yaml api/response.py                                      T4
│   ├── incidents.py dora.py llm.py config/dora_profile.yaml
│   │   config/dependencies.yaml api/incidents.py                                 T5
│   ├── api/demo.py                                                               T2
│   ├── api/metrics.py                                                            T7
│   └── tests/test_tN_*.py                                                        TN (one prefix per task)
├── evaluation/                  T7 (except evaluation/__init__.py, created by T0)
├── frontend/                    T6 (except frontend/src/types.ts, owned by T0: mirror of models.py)
├── fixtures/                    T0 (other tasks may ADD files, never modify existing ones)
├── infra/ .github/workflows/    T8
├── docs/                        T9 (final README, playbook, compliance, defense sheet, deck, video)
│   └── contract-requests.md     everyone (contract change requests)
└── data/                        generated at runtime, ignored by git except data/eval/metrics.json
```

## 1.6 Collaboration rules (anti-friction)

1. **Contract first.** Section 2 of this document, `backend/models.py` and `fixtures/` are frozen. Any change request goes through `docs/contract-requests.md` (see 2.12).
2. **Everyone owns their files.** Never touch a file owned by another task. T0 files only change via the process in 2.12.
3. **Work alone on mocks.** Front on fixtures, detectors on recorded series, response in dry-run, scripts on anvil. Nobody waits for anybody.
4. **Same commands for everyone.** `make <cible>` (section 2.10). Each task adds its targets in its `mk/tN.mk`, never in the root `Makefile`.
5. **Branches and commits.** One branch per task, small PRs to `main`, `make test` green before merge, frequent pushes after each green test (AWS rule: the account is wiped at the end of the event).
6. **Secrets.** No key in the repo (the jury checks). Keys in `.env` (ignored). `gitleaks` in pre-commit. One key per role (2.1), to avoid nonce conflicts.
7. **Language.** Code, names, API, UI, README: English. Internal docs: French.
8. **AWS and Fuji usage rules.** Only test and attack what we deployed ourselves. Synthetic data only. No jailbreaking of Bedrock models. Less than one Bedrock request per second per person.
