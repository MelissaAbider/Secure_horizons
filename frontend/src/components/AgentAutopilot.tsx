import { useState } from 'react'
import { api, ApiError } from '../api'
import { usePolling } from '../hooks/usePolling'
import { formatUsd, formatUtc, shortHash } from '../lib/format'
import type { AgentCycle, AgentMoveRecord } from '../types'
import { Pill } from './ui'

// The allocation agent at work: Claude on Bedrock reads the markets through MCP tools and proposes moves; the
// platform re-reads the chain and the signed rules, then executes, asks for a signature, or refuses. Everything
// shown here comes from the backend (/api/agent/*).

const CARD = 'rounded-2xl border border-ink-700 bg-white p-5'
const BTN = 'inline-flex items-center justify-center gap-2 rounded-2xl bg-fog-100 px-5 py-3 text-[15px] font-semibold text-ink-950 transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40'
const BTN_LIGHT = 'inline-flex items-center justify-center gap-2 rounded-2xl border border-ink-700 bg-white px-4 py-2 text-[14px] font-semibold text-fog-100 transition hover:border-fog-500 disabled:cursor-not-allowed disabled:opacity-40'
const INTERVAL_S = 30

const STATUS: Record<AgentMoveRecord['status'], { label: string; tone: 'ok' | 'warn' | 'bad' | 'neutral' | 'violet' }> = {
  executed: { label: 'executed', tone: 'ok' },
  simulated: { label: 'approved · dry run', tone: 'ok' },
  executing: { label: 'executing…', tone: 'neutral' },
  awaiting_signature: { label: 'needs signature', tone: 'violet' },
  refused: { label: 'refused', tone: 'bad' },
  refused_onchain: { label: 'refused on-chain', tone: 'bad' },
  failed: { label: 'failed', tone: 'bad' },
}

function explorerTx(hash: string, network?: string) {
  return network === 'fuji'
    ? <a key={hash} href={`https://testnet.snowtrace.io/tx/${hash}`} target="_blank" rel="noreferrer" className="font-mono text-signal-violet hover:underline">{shortHash(hash)} ↗</a>
    : <span key={hash} className="font-mono">{shortHash(hash)}</span>
}

function MoveRow({ m, onApprove, busy }: { m: AgentMoveRecord; onApprove: (id: string) => void; busy: boolean }) {
  const s = STATUS[m.status]
  return (
    <li className="rounded-xl border border-ink-700 p-3 text-[13px]" data-testid="agent-move">
      <div className="flex items-center justify-between gap-3">
        <b>{m.action} {Number(m.amount).toLocaleString('en-US')} {m.asset} {m.action === 'deposit' ? 'on' : 'from'} {m.protocol}</b>
        <span className="flex gap-1.5">{m.paper && <Pill tone="warn">paper</Pill>}<Pill tone={s.tone}>{s.label}</Pill></span>
      </div>
      <div className="mt-1 text-fog-400">{formatUtc(m.at)} · block {m.block_number.toLocaleString('en-US')} · {formatUsd(m.value_usd)} · by {m.source === 'mcp' ? 'MCP client' : m.source === 'fallback' ? 'fallback planner' : 'Claude'}</div>
      {m.reason && <div className="mt-1 italic text-fog-300">“{m.reason}”</div>}
      <ul className="mt-1 list-disc pl-5 text-fog-400">{m.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      {m.txs.length > 0 && <div className="mt-1 flex flex-wrap gap-2">{m.txs.map((t) => explorerTx(t, 'fuji'))}</div>}
      {m.detail && <div className="mt-1 text-fog-400">{m.detail}</div>}
      {m.status === 'awaiting_signature' && (
        <button data-testid="agent-approve" disabled={busy} onClick={() => onApprove(m.id)} className={`${BTN_LIGHT} mt-2`}>Sign and execute</button>
      )}
    </li>
  )
}

function CycleCard({ c }: { c: AgentCycle }) {
  return (
    <div className="rounded-xl border border-ink-700 p-4 text-[13px]" data-testid="agent-cycle">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b>{c.id}</b>
        <span className="text-fog-400">{formatUtc(c.started_at)} · {c.source === 'bedrock' ? `Claude (${c.model})` : c.source === 'fallback' ? 'fallback planner' : 'no data'} · {c.trigger}</span>
      </div>
      {c.summary && <p className="mt-2 text-[14px]">{c.summary}</p>}
      {c.error && <p className="mt-1 text-amber-700">{c.error}</p>}
      <ol className="mt-2 flex flex-wrap gap-1.5 font-mono text-[11px]">
        {c.steps.map((s, i) => (
          <li key={i} className={`rounded border px-2 py-0.5 ${s.tool === 'propose_allocation' ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-ink-600 text-fog-300'}`}>
            {i + 1}. {s.tool}
          </li>
        ))}
      </ol>
      <div className="mt-2 font-mono text-[11px] text-fog-500">record_hash {shortHash(c.record_hash)}</div>
    </div>
  )
}

export function AgentAutopilot({ instructions }: { instructions: string }) {
  const status = usePolling(() => api.agentStatus(), 5000)
  const cycles = usePolling(() => api.agentCycles(), 3000)
  const moves = usePolling(() => api.agentMoves(), 3000)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string>()
  const st = status.data

  async function act(call: () => Promise<unknown>) {
    setBusy(true); setMsg(undefined)
    try { await call() } catch (e) { setMsg(e instanceof ApiError ? e.detail : String(e)) } finally { setBusy(false) }
  }

  return (
    <section data-testid="agent-autopilot" className="mt-6 rounded-[28px] border border-white bg-white/75 p-7 shadow-[0_20px_60px_-30px_rgba(21,27,46,.25)] backdrop-blur sm:p-9">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <div className="font-mono text-[12px] font-medium uppercase tracking-[0.24em] text-fog-400">Allocation agent</div>
          <h2 className="mt-3 font-display text-[26px] font-semibold tracking-[-0.02em]">The agent picks the markets, the rules decide</h2>
          <p className="mt-2 max-w-2xl text-[15px] text-fog-400">
            Claude reads the markets, the Safe and the alerts through MCP tools, then proposes moves. The platform re-reads the chain and the signed rules: inside the list and the caps it executes, above {formatUsd(Number(st?.rules?.human_signature_above_usd ?? 100000))} a human signs, anything else is refused. The agent holds no key.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {st && <Pill tone={st.model_configured ? 'ok' : 'warn'}>{st.model_configured ? `Bedrock · ${st.region}` : 'no model: fallback planner'}</Pill>}
            {st && <Pill tone={st.dry_run ? 'warn' : 'ok'}>{st.dry_run ? 'dry run: nothing sent' : 'live on Fuji'}</Pill>}
            {st?.loop && <Pill tone="violet">auto · every {st.interval_s}s</Pill>}
            {st?.running && <Pill>thinking…</Pill>}
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <button data-testid="agent-run" disabled={busy || st?.running} onClick={() => void act(() => api.agentRun(instructions))} className={BTN}>
            {busy || st?.running ? 'Agent at work…' : 'Let the agent manage'} <span aria-hidden>→</span>
          </button>
          <button data-testid="agent-loop" disabled={busy || !st} onClick={() => void act(() => api.agentLoop(!st?.loop, INTERVAL_S, instructions))} className={BTN_LIGHT}>
            {st?.loop ? 'Stop autopilot' : `Autopilot every ${INTERVAL_S}s`}
          </button>
        </div>
      </div>
      {msg && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">{msg}</p>}
      {status.error && <p className="mt-4 text-[13px] text-fog-400">Agent API unreachable: start the backend.</p>}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className={CARD}>
          <b>Moves and verdicts</b>
          {(moves.data ?? []).length === 0
            ? <p className="mt-3 text-fog-400">No proposal yet. Click “Let the agent manage”.</p>
            : <ul className="mt-3 space-y-2">{(moves.data ?? []).slice(0, 12).map((m) => (
                <MoveRow key={m.id} m={m} busy={busy} onApprove={(id) => void act(() => api.agentApprove(id, 'asset manager (dashboard)'))} />
              ))}</ul>}
        </div>
        <div className={CARD}>
          <b>Agent cycles</b>
          {(cycles.data ?? []).length === 0
            ? <p className="mt-3 text-fog-400">Each cycle shows the tools the agent called, its summary and the hash of its record.</p>
            : <div className="mt-3 space-y-2">{(cycles.data ?? []).slice(0, 6).map((c) => <CycleCard key={c.id} c={c} />)}</div>}
        </div>
      </div>
    </section>
  )
}
