// Talk to the Treasury Guard agent (Amazon Bedrock AgentCore) through our backend: POST /api/agent/ask.
// The agent only proposes; the backend re-checks the proposal against the signed rules.
import { API_URL, ApiError, isFixtureMode } from '../api'

export type AgentVerdict = 'executed' | 'signature' | 'blocked'
export interface AgentProposal { action?: string; protocol?: string; amount_usd?: number; allowed?: boolean; reason?: string }
export interface AgentAnswer { session_id: string; proposal: AgentProposal; verdict: AgentVerdict; reasons: string[]; raw: string }

// Offline answer for fixture mode / previews, following the same rules as the real guard.
function mock(prompt: string, sid: string | null): AgentAnswer {
  const p = prompt.toLowerCase()
  const bait = /new protocol|nouveau|incident|audited|14\s*%/.test(p)
  const amount = Number(p.replace(/[,\s]/g, '').match(/(\d{5,})/)?.[1] ?? 50000)
  const proposal: AgentProposal = bait
    ? { action: 'none', protocol: 'unknown', amount_usd: 0, allowed: false, reason: 'Not on the sealed list or above the 40% cap. Refused.' }
    : { action: 'move', protocol: 'Benqi USDC', amount_usd: Math.min(amount, 300000), allowed: true, reason: 'Rebalance so no protocol holds more than 40%.' }
  const verdict: AgentVerdict = bait ? 'blocked' : (proposal.amount_usd ?? 0) > 100000 ? 'signature' : 'executed'
  const reasons = bait ? ['agent itself refused', 'not on the sealed list'] : verdict === 'signature' ? ['above $100,000: human signature needed'] : ['on the list, under every cap']
  return { session_id: sid ?? 'fixture-session-000000000000000000000', proposal, verdict, reasons, raw: JSON.stringify(proposal) }
}

export async function askAgent(prompt: string, sessionId: string | null): Promise<AgentAnswer> {
  if (isFixtureMode()) { await new Promise((r) => setTimeout(r, 600)); return mock(prompt, sessionId) }
  const res = await fetch(`${API_URL}/api/agent/ask`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, session_id: sessionId }),
  })
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); if (typeof j?.detail === 'string') detail = j.detail } catch { /* not json */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<AgentAnswer>
}
