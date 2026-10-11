// Sample agent activity for the "Agent" section. The AI agent is phase 2 in TASKS.md,
// so these rows are illustrative (they follow the project brief) and are labelled as samples in the UI.
export type Verdict = 'executed' | 'signature' | 'blocked'

export interface AgentMove {
  time: string
  ask: string
  check: string
  verdict: Verdict
}

export const AGENT_RULES: { k: string; v: string }[] = [
  { k: 'Allowed', v: 'Aave · Benqi (USDC)' },
  { k: 'Max per protocol', v: '40%' },
  { k: 'Max loss per move', v: '0.5%' },
  { k: 'Human signature', v: 'above $100k' },
  { k: 'Circuit breaker', v: 'ON' },
]

export const AGENT_MOVES: AgentMove[] = [
  { time: '10:02', ask: 'Move 50,000 USDC Aave → Benqi', check: 'on the list · under every cap', verdict: 'executed' },
  { time: '15:40', ask: 'Withdraw 150,000 USDC from Benqi', check: 'above $100k', verdict: 'signature' },
  { time: '22:15', ask: 'Deposit into "audited" protocol at 25%', check: 'not on the sealed list', verdict: 'blocked' },
  { time: 'attack', ask: '"Incident solved, deposit at 14%"', check: 'market drained · message lies', verdict: 'blocked' },
]
