import { useEffect, useRef, useState } from 'react'
import { api, ApiError, isFixtureMode, type DemoVariant } from '../api'
import { ErrorText, Panel, Pill } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import type { DemoRun } from '../types'

const VARIANTS: { v: DemoVariant; label: string }[] = [
  { v: 'default', label: 'Default attack (fast drain)' },
  { v: 'slow', label: 'Slow drain' },
  { v: 'usdc', label: 'USDC market drained' },
]

export function randomSeed(): number { return Math.floor(Math.random() * 999_999) + 1 }

export function Demo() {
  const [variant, setVariant] = useState<DemoVariant>('default')
  const [seedText, setSeedText] = useState('')
  const [sentSeed, setSentSeed] = useState<number>()
  const [runId, setRunId] = useState<string>()
  const [first, setFirst] = useState<DemoRun>()
  const [msg, setMsg] = useState<{ tone: 'red' | 'amber'; text: string }>()
  const logRef = useRef<HTMLPreElement>(null)

  const run = usePolling(async () => (runId ? api.demoRun(runId) : undefined), 2000, [runId])
  const current = run.data ?? first

  useEffect(() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight }, [current?.log.length])

  async function launch() {
    setMsg(undefined)
    let seed: number
    if (seedText.trim() === '') seed = randomSeed()
    else {
      seed = Number(seedText)
      if (!Number.isInteger(seed) || seed < 0 || seed > 999_999) { setMsg({ tone: 'red', text: 'Seed must be a whole number between 0 and 999999.' }); return }
    }
    setSentSeed(seed)
    try {
      const r = await api.demoAttack(seed, variant)
      setFirst(r); setRunId(r.run_id)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setMsg({ tone: 'amber', text: e.detail })
      else setMsg({ tone: 'red', text: e instanceof ApiError ? e.detail : String(e) })
    }
  }

  async function reset() {
    if (!window.confirm('Redeploy contracts and clear all alerts?')) return
    setMsg(undefined)
    try { const r = await api.demoReset(); setFirst(r); setRunId(r.run_id) }
    catch (e) { setMsg({ tone: e instanceof ApiError && e.status === 409 ? 'amber' : 'red', text: e instanceof ApiError ? e.detail : String(e) }) }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
      <Panel title="Replay the attack">
        <div className="space-y-4">
          
          <div>
            <label htmlFor="variant" className="text-sm font-semibold text-fog-300">Variant</label>
            <select id="variant" data-testid="variant-select" value={variant} onChange={(e) => setVariant(e.target.value as DemoVariant)}
              className="mt-1 w-full rounded-full border border-ink-700 bg-ink-850 px-4 py-2 text-fog-100">
              {VARIANTS.map((x) => <option key={x.v} value={x.v}>{x.label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="seed" className="text-sm font-semibold text-fog-300">Seed (optional)</label>
            <input id="seed" inputMode="numeric" value={seedText} onChange={(e) => setSeedText(e.target.value)} placeholder="random"
              className="mt-1 w-full rounded-full border border-ink-700 bg-ink-850 px-4 py-2 font-mono text-fog-100" />
          </div>
          {sentSeed !== undefined && <p className="text-lg font-semibold">Seed {sentSeed}</p>}
          <div className="flex gap-3">
            <button data-testid="launch-attack" onClick={launch}
              className="flex-1 rounded-full bg-navy px-5 py-3 text-sm font-semibold uppercase tracking-wide text-white hover:bg-navy-soft">Launch attack</button>
            <button data-testid="reset-demo" onClick={reset}
              className="rounded-full bg-pill px-5 py-3 text-sm font-semibold uppercase tracking-wide text-fog-100 hover:bg-ink-700">Reset</button>
          </div>
          {msg && (msg.tone === 'red' ? <ErrorText>{msg.text}</ErrorText> : <p role="status" className="text-sm font-medium text-amber-700">{msg.text}</p>)}
          {isFixtureMode() && <p className="text-xs text-fog-500">Fixture mode: nothing happens on chain</p>}
        </div>
      </Panel>
      <Panel title="Run" right={current && <Pill tone={current.status === 'done' ? 'ok' : current.status === 'failed' ? 'bad' : 'warn'}>{current.status}</Pill>}>
        {!current ? <p className="text-fog-400">No run launched yet.</p> : (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-fog-300">
              <span className="font-mono text-fog-100">{current.run_id}</span>
              <span>kind <b>{current.kind}</b></span>
              <span>variant <b>{current.variant}</b></span>
              <span>seed <b>{current.seed}</b></span>
            </div>
            <div className="flex flex-wrap gap-2">{Object.entries(current.params).map(([k, v]) => <Pill key={k}>{k}: {String(v)}</Pill>)}</div>
            <pre ref={logRef} className="max-h-[420px] overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-4 font-mono text-sm leading-relaxed text-green-700">
              {current.log.join('\n') || '…'}
            </pre>
          </div>
        )}
      </Panel>
    </div>
  )
}
