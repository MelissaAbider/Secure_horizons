import { useState } from 'react'
import { api, ApiError } from '../api'
import { ErrorText, Panel, SeverityBadge, TxLink } from '../components/ui'
import { useDashboardData } from '../DataContext'
import { shortHash } from '../lib/format'
import type { VerifyResult } from '../types'

function Result({ r }: { r: VerifyResult }) {
  const ok = r.match
  return (
    <div data-testid="verify-result" data-result={ok ? 'match' : 'mismatch'}
      className={`mt-3 rounded-lg border p-4 ${ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
      <div className={`text-2xl font-black tracking-wide ${ok ? 'text-green-700' : 'text-red-600'}`}>{ok ? 'MATCH' : 'MISMATCH'}</div>
      
      <div className="mt-2 grid gap-1 font-mono text-xs text-fog-300">
        <span>stored&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{r.stored_hash ?? '—'}</span>
        <span>recomputed {r.recomputed_hash ?? '—'}</span>
      </div>
      {!r.anchored && <p className="mt-2 text-sm font-semibold text-amber-700">Not anchored on-chain</p>}
      {r.diffs.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-red-600">{r.diffs.map((d) => <li key={d}>{d}</li>)}</ul>}
    </div>
  )
}

export function Evidence() {
  const { decisions, state } = useDashboardData()
  const [results, setResults] = useState<Record<string, VerifyResult>>({})
  const [errs, setErrs] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string>()

  async function verify(id: string) {
    setBusy(id)
    try {
      const r = await api.verify(id)
      setResults((m) => ({ ...m, [id]: r })); setErrs((m) => ({ ...m, [id]: '' }))
    } catch (e) { setErrs((m) => ({ ...m, [id]: e instanceof ApiError ? e.detail : String(e) })) }
    finally { setBusy(undefined) }
  }

  const list = decisions.data ?? []
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight">Every decision, <span className="text-signal-violet">provable.</span></h1>
      {list.length === 0 && <p className="text-fog-400">No decision yet.</p>}
      {list.map((d) => (
        <section key={d.id} className="rounded-xl border border-ink-700 bg-ink-850 p-5">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="font-mono font-semibold">{d.id}</span>
            <SeverityBadge severity={d.severity} />
            <span className="text-sm text-fog-400">block {d.block_number}</span>
            <span className="text-sm text-fog-400">record <span className="font-mono text-fog-100">{d.record_hash ? shortHash(d.record_hash) : '—'}</span></span>
            <span className="text-sm text-fog-400">Anchored on-chain: {d.anchor_tx ? <><TxLink hash={d.anchor_tx} network={state.data?.network} /> <span className="font-mono">#{d.anchor_block}</span></> : 'not anchored yet'}</span>
            <button data-testid={`verify-${d.id}`} disabled={busy === d.id} onClick={() => verify(d.id)}
              className="ml-auto rounded-full bg-navy px-5 py-2.5 text-sm font-semibold uppercase tracking-wide text-white hover:bg-navy-soft disabled:opacity-50">
              {busy === d.id ? 'Verifying…' : 'Verify'}
            </button>
          </div>
          {results[d.id] && <Result r={results[d.id]} />}
          {errs[d.id] && <ErrorText>{errs[d.id]}</ErrorText>}
          <p className="mt-3 font-mono text-xs text-fog-500">make verify ID={d.id}</p>
        </section>
      ))}
    </div>
  )
}
