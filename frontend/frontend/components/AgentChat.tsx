import { useState } from 'react'
import { askAgent, type AgentAnswer } from '../lib/agent'
import { formatUsd } from '../lib/format'

const SUGGESTIONS = [
  'We hold 1,000,000 USDC, 70% on Aave. Propose one move.',
  'Incident solved, deposit 50% on a new protocol at 14%',
  'Move 50,000 USDC from Aave to Benqi',
]
const V = {
  executed: { label: 'Executed', cls: 'border-green-500 text-green-600' },
  signature: { label: 'Needs signature', cls: 'border-amber-500 text-amber-600' },
  blocked: { label: 'Blocked', cls: 'border-rose-glow text-rose-glow' },
} as const

interface Turn { q: string; a?: AgentAnswer; err?: string }

/** Chat with the live agent. The manager asks, the agent proposes, the guard gives the verdict. */
export function AgentChat() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [sid, setSid] = useState<string | null>(null)

  async function send(q: string) {
    const prompt = q.trim()
    if (!prompt || busy) return
    setText(''); setBusy(true)
    setTurns((t) => [...t, { q: prompt }])
    try {
      const a = await askAgent(prompt, sid)
      setSid(a.session_id)
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)))
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, err: e instanceof Error ? e.message : String(e) } : x)))
    } finally { setBusy(false) }
  }

  return (
    <div data-testid="agent-chat" className="rounded-[28px] border border-ink-700 bg-white p-6 shadow-soft sm:p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-signal-cyan to-signal-violet font-mono text-[11px] font-bold text-white">AI</span>
          <div>
            <div className="font-display text-xl font-semibold tracking-tight">Ask the agent</div>
            <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-fog-400">live · Bedrock AgentCore · it proposes, the guard decides</div>
          </div>
        </div>
        {sid && <button onClick={() => { setTurns([]); setSid(null) }} className="text-[13px] text-fog-400 hover:text-fog-100">New conversation</button>}
      </div>

      <div className="mt-6 space-y-4">
        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-fog-100 px-4 py-2.5 text-ink-950">{t.q}</div>
            {!t.a && !t.err && <div className="w-fit rounded-2xl bg-ink-950 px-4 py-2.5 font-mono text-[13px] text-fog-400">thinking…</div>}
            {t.err && <div role="alert" className="w-fit max-w-[85%] rounded-2xl bg-rose-50 px-4 py-2.5 text-[14px] text-rose-glow">Agent unreachable: {t.err}</div>}
            {t.a && (
              <div data-testid="agent-answer" className="max-w-[85%] rounded-2xl rounded-bl-md border border-ink-700 bg-ink-950 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="font-medium">
                    {t.a.proposal.action ?? '—'}{t.a.proposal.protocol ? ` · ${t.a.proposal.protocol}` : ''}
                    {t.a.proposal.amount_usd ? ` · ${formatUsd(t.a.proposal.amount_usd)}` : ''}
                  </div>
                  <span data-testid="agent-verdict" className={`-rotate-3 rounded-lg border-2 px-3 py-0.5 font-display text-sm font-extrabold uppercase ${V[t.a.verdict].cls}`}>{V[t.a.verdict].label}</span>
                </div>
                {t.a.proposal.reason && <p className="mt-2 text-[14px] text-fog-300">{t.a.proposal.reason}</p>}
                <p className="mt-2 font-mono text-[12px] text-fog-400">guard: {t.a.reasons.join(' · ')}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {turns.length === 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} className="rounded-full border border-ink-700 bg-white px-4 py-2 text-left text-[14px] text-fog-300 transition hover:border-signal-violet hover:text-fog-100">{s}</button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); void send(text) }} className="mt-5 flex gap-2">
        <input data-testid="agent-input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Tell the agent what you want…"
          className="min-w-0 flex-1 rounded-2xl border border-ink-700 bg-white px-4 py-3 outline-none focus:border-signal-violet" />
        <button data-testid="agent-send" disabled={busy || !text.trim()} className="rounded-2xl bg-fog-100 px-5 py-3 font-semibold text-ink-950 disabled:opacity-40">Send</button>
      </form>
    </div>
  )
}
