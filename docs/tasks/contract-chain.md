# Contract: chain side

> Light version of `TASKS.md` (full detail there). Same numbering, so a reference like "2.7" means the same thing in both.

### 2.1 Networks, roles and environment variables

`NETWORK=local` (anvil) or `NETWORK=fuji`. All code reads the environment through `backend/settings.py`.

| Variable | Use | Required by |
|---|---|---|
| `NETWORK` | `local` or `fuji` | all |
| `RPC_URL` | network RPC (local default `http://127.0.0.1:8545`; for fuji, a provider URL, the public RPC is rate-limited) | all |
| `RPC_FALLBACK_URL` | fallback RPC (`https://api.avax-test.network/ext/bc/C/rpc`) | T3, T4 |
| `CHAIN_ID` | 31337 or 43113 (derived from `NETWORK` if missing) | all |
| `EXPLORER_URL` | `https://testnet.snowtrace.io` | T4, T6 |
| `DEPLOYER_PK` | deploys, mints test tokens, sets prices | T1, T2 |
| `OWNER_PK` | vault owner (represents the Safe signers) | T1, T2, T4 |
| `GUARDIAN_PK` | **our platform's** key: pause deposits and emergency withdrawal, nothing else | T4 |
| `PROTOCOL_GUARDIAN_PK` | lending protocol guardian (freeze at the end of the scenario) | T2 |
| `ATTACKER_PK` | attacker | T2 |
| `EVIDENCE_PK` | anchors hashes in `EvidenceRegistry` | T4 |
| `BOT_PKS` | 3 comma-separated keys (normal users) | T2 |
| `USE_FIXTURES` | `true`: the API serves fixtures; `false`: real data | T3, T4, T5 |
| `ENGINE_ENABLED` | `true`: the monitoring loop runs at backend startup | T3 |
| `POLL_INTERVAL_S` | read interval (default 2) | T3 |
| `DRY_RUN_ACTIONS` | `true`: the response sends no transaction | T4 |
| `AWS_REGION` | `us-east-1` | T4, T5, T8 |
| `SNS_TOPIC_ARN` | alerts topic (empty = disabled) | T4, T8 |
| `ALERT_WEBHOOK_URL` | Slack/Discord webhook (empty = disabled) | T4 |
| `EVIDENCE_BUCKET` | S3 evidence bucket (empty = local only) | T4, T8 |
| `BEDROCK_MODEL_ID` | Claude model on Bedrock (empty = report without AI) | T5, T8 |
| `ETH_ARCHIVE_RPC_URL` | Ethereum archive RPC (phase 2, replay of the real incident) | T7 |
| `VITE_API_URL` | API base for the front; empty in production (same origin, nginx serves `/api`), `http://localhost:8000` in development | T6, T8 (in `frontend/.env.example`) |
| `VITE_USE_FIXTURES` | `true`: the front reads `fixtures/` without a backend | T6 |

**On `local`, no key to write**: `settings.private_key(role)` falls back to anvil's public accounts (mnemonic `test test … junk`): deployer = index 0, owner = 1, guardian = 2, protocol_guardian = 3, attacker = 4, evidence = 5, bots = 6, 7, 8.

### 2.2 Solidity contracts (summary)

Exact signatures, events and revert messages: `TASKS.md` 2.2.

| Contract | What matters |
|---|---|
| `MockERC20` | USDC (6 decimals), WETH (18); `mint(to, amount)` by the owner |
| `RsETH` | 18 decimals; mint and burn only by the bridge |
| `MockBridge` | `deposit(weth)` mints backed rsETH; `forgedRelease(to, amount)` is **the flaw** (mints without backing, callable by anyone); `totalBacking()`, `backingRatioBps()` |
| `MockOracle` | `setPriceE8` / `getPriceE8`, USD with 8 decimals |
| `MiniLend` x2 (`lend-eth`, `lend-avax`) | `supply`, `withdraw` (max = min(position, liquidity), 0 without revert if nothing), `depositCollateral`, `borrow` (collateral × LTV check via the oracle), `repay` (capped at the debt). Protocol guardian: `listReserve`, `setReserveFrozen`, `setReservePaused`, `setLtv`. Reads: `getAssets`, `getReservesData`, `getUserSupplied/Collateral/Borrowed`. Frozen = withdraw and repay still work; paused = everything blocked. Lending balance and collateral balance are separate. |
| `TreasuryVault` | `owner` stands for the Safe signers; `guardian` is our platform and can only tighten. `supply`/`withdraw` (owner, from the vault's own balance), `emergencyWithdraw(market, asset)` (owner or guardian, always back to the vault, 0 with event if nothing), `pauseDeposits` (owner or guardian, idempotent), `unpauseDeposits` (owner only) |
| `EvidenceRegistry` | `anchor(hash, kind, uri)` with kind in decision, rules, incident; `anchoredAt(hash)` gives the block (0 if never) |

Rate model (same in fixtures): kink at 80 % utilization; at 100 %, borrow 7900 bps and supply 6715 bps (the bait yield).

**Initial deployment parameters** (fixed so that fixtures, tests and demo match):

| Item | Value |
|---|---|
| Oracle prices | USDC = $1.00; WETH = $2,500; rsETH = $2,500 |
| Reserves of `lend-eth` and `lend-avax` | USDC (borrowable and collateral, LTV 8,000 bps), WETH (borrowable and collateral, LTV 8,000 bps), rsETH (collateral only, LTV 7,500 bps). Lending side and collateral side are two separate balances: collateral does not add to borrowable liquidity. |
| Initial liquidity `lend-eth` | WETH: 2,000 supplied of which 150 by the vault, 1,200 borrowed (utilization 60%); USDC: 3,000,000 supplied of which 400,000 by the vault, 1,800,000 borrowed |
| Initial liquidity `lend-avax` | WETH: 1,000 supplied of which 100 by the vault, 550 borrowed; USDC: 2,000,000 supplied of which 300,000 by the vault, 1,100,000 borrowed |
| Collateral of normal borrowers (bots) | `lend-eth`: 900 rsETH + 4,500,000 USDC (capacity $5,287,500 for $4,800,000 borrowed); `lend-avax`: 300 rsETH + 3,000,000 USDC (capacity $2,962,500 for $2,475,000 borrowed) |
| rsETH before the attack | 1,200 in circulation, 1,200 WETH of backing (100%); 900 as collateral on `lend-eth`, 300 on `lend-avax` |
| Default attack | `forgedRelease` of 5,000 rsETH, collateral deposit on `lend-eth`, borrows of 100 WETH per chunk every 8 s until exhausted, 2 withdrawals of 100 WETH by bots during the draining, freeze of rsETH by the protocol guardian at the end of the scenario |

### 2.3 `deployments/<network>.json` file (written by T1, read by everyone)

```json
{
  "network": "fuji",
  "chain_id": 43113,
  "deployed_at_block": 45201700,
  "explorer": "https://testnet.snowtrace.io",
  "assets": { "USDC": "0x…", "WETH": "0x…", "rsETH": "0x…" },
  "contracts": { "MockBridge": "0x…", "MockOracle": "0x…", "TreasuryVault": "0x…", "EvidenceRegistry": "0x…" },
  "lending": [
    { "id": "lend-eth",  "label": "Lending protocol, Ethereum deployment (simulated)",  "address": "0x…" },
    { "id": "lend-avax", "label": "Lending protocol, Avalanche deployment (simulated)", "address": "0x…" }
  ],
  "roles": { "deployer": "0x…", "owner": "0x…", "guardian": "0x…", "protocol_guardian": "0x…",
             "attacker": "0x…", "evidence": "0x…", "bots": ["0x…", "0x…", "0x…"] }
}
```

ABIs: `abi/MockERC20.json`, `abi/RsETH.json`, `abi/MockBridge.json`, `abi/MockOracle.json`, `abi/MiniLend.json`, `abi/TreasuryVault.json`, `abi/EvidenceRegistry.json` (format: the raw JSON ABI list).

### 2.4 Shared Python helpers (`backend/chain.py`, T0)

All Python code goes through these functions (nobody rewrites their own ABI loading or nonce handling).

```python
def w3() -> Web3                                   # client for the current network (RPC_URL)
def load_deployment() -> dict                      # re-reads deployments/<network>.json on every call (a redeploy is picked up)
def load_abi(name: str) -> list                    # abi/<name>.json
def token(symbol: str) -> Contract                 # "USDC" | "WETH" | "rsETH" (ABI MockERC20, RsETH for rsETH)
def lending(deployment_id: str) -> Contract        # "lend-eth" | "lend-avax" (ABI MiniLend)
def vault() -> Contract                            # TreasuryVault
def bridge() -> Contract                           # MockBridge
def oracle() -> Contract                           # MockOracle
def registry() -> Contract                         # EvidenceRegistry
def account(role: str) -> LocalAccount             # "deployer" | "owner" | "guardian" | "protocol_guardian" | "attacker" | "evidence"
def bot_accounts() -> list[LocalAccount]
def send(fn, sender: LocalAccount, value: int = 0) -> dict
    # builds, signs, sends, waits for the receipt; one lock per sender avoids nonce conflicts
    # returns {"tx_hash": "0x…", "status": 1|0, "block_number": int, "gas_used": int}
def explorer_tx(tx_hash: str) -> str               # snowtrace link
```
