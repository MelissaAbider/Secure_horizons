# Sunday scope

One demo, one story. If a task does not serve that story, it waits.

## In the demo

1. Connect a test Safe on Fuji.
2. Select Aave USDC and Benqi USDC, generate an operation list, seal it with test signers.
3. Configuration: guaranteed rules separated from instructions.
4. Agent proposes a normal move, accepted only if the list and the caps pass.
5. Fast-forward replay of the April 2026 incident: fake collateral, run, empty reserve.
6. Circuit breaker: freeze new deposits, pull back to the vault what can still exit.
7. 14% "incident resolved" bait: order is on the list, blocked after an on-chain reread.
8. Signed, replayable decision. DORA draft not sent.

## Explicitly later

- Protocols other than the two in the demo.
- Real Telegram or Slack integration beyond a pause / alert channel.
- Automatic filing of a report.
- Yield optimization as the main product.
- Mainnet, external audit, or production key management.

## Open decisions

The group decides these. An agent does not:

- language and framework
- who holds the teller-window key in the demo, and how it is isolated
- exact operation leaf format in the Merkle tree
- where proofs live (file, database, anchor)
- which agent model runs on Sunday
