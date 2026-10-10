# Sources

Do not cite an incident fact without a row here. Facts that affect code need a primary or clearly marked secondary source before evaluation is frozen.

| Fact | Source | Status |
| --- | --- | --- |
| Product brief: Aave/KelpDAO incident framing, cross-chain freeze, treasury reaction window | `projet-en-bref.pdf`, page 5 | accepted product source |
| Bridge accepted a forged cross-chain message and released approximately 116,500 rsETH; Kelp paused roughly 46 minutes later; Aave froze rsETH markets | https://www.theblock.co/news/regulation/2026-04-18-kelp-daos-rseth-bridge-apparently-exploited-for-roughly-292-million-in-layerzero-based-attack-397988 | secondary report; use for mechanism, not final loss |
| The rsETH was used as lending collateral to borrow WETH; Aave contracts were not the exploited component | https://beincrypto.com/aave-weth-rseth-exploit-withdraw-warning/ | secondary corroboration |
| Detailed claim that destination nonce 308 was accepted while source nonce remained 307 | https://oakresearch.io/en/analyses/investigations/kelp-dao-hack-full-picture-of-292-million-disaster | secondary forensic report; verify against canonical transactions before final evaluation |
| Block-by-block replay and canonical source/destination events | public Ethereum and source-chain RPC data, transaction list not yet indexed in the repo | required before measurement freeze |

Implementation conclusion: R1 monitors bridge conservation and nonce consistency. `backing_ratio_bps` is not used as the root-cause detector.
