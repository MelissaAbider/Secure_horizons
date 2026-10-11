import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Banner, Panel, Stat } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { formatPct, formatRate, formatTtd } from '../lib/format'

const n = (v: unknown): number | undefined => (typeof v === 'number' ? v : undefined)

export function Metrics() {
  const m = usePolling(() => api.metrics(), 30000)
  if (!m.data) return m.error ? <p className="text-red-600">Could not load metrics: {m.error.message}</p> : <p className="text-fog-400">Loading…</p>
  const s = m.data.synthetic
  const runsA = n(s.runs_attack) ?? 0
  const saved = n(s.saved_pct_mean)
  const base = n(s.baseline_saved_pct_mean)
  const fmt = (v: number | undefined, f: (x: number) => string) => (v === undefined ? '—' : f(v))
  return (
    <div className="space-y-4">
      {runsA === 0 && <Banner tone="amber">No evaluation run yet (fixture values)</Banner>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Detection rate" value={fmt(n(s.detection_rate), formatRate)} accent="ok" />
        <Stat label="False positive rate" value={fmt(n(s.false_positive_rate), formatRate)} />
        <Stat label="Time to detect p50 / p90" value={<span className="text-2xl">{fmt(n(s.ttd_blocks_p50), formatTtd)} / {fmt(n(s.ttd_blocks_p90), formatTtd)}</span>} />
        <Stat label="Runs (attack / normal)" value={`${runsA} / ${n(s.runs_normal) ?? '—'}`} />
      </div>
      <Panel title="Saved: with us vs. without">
        <div className="grid items-center gap-6 md:grid-cols-[1fr_2fr]">
          <div className="space-y-3">
            <div><div className="text-xs uppercase tracking-wider text-fog-400">Saved with us</div><div className="text-4xl font-bold text-green-700">{fmt(saved, formatPct)}</div></div>
            <div><div className="text-xs uppercase tracking-wider text-fog-400">Saved without us</div><div className="text-4xl font-bold text-fog-300">{fmt(base, formatPct)}</div></div>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[{ name: 'With us', v: saved ?? 0 }, { name: 'Without us', v: base ?? 0 }]} layout="vertical" margin={{ left: 20, right: 20 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#7A8396' }} tickFormatter={(v: number) => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#F1F3F7' }} width={90} />
                <Bar dataKey="v" radius={[0, 6, 6, 0]} isAnimationActive={false}>
                  <Cell fill="#19A7FF" /><Cell fill="#2A3242" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>
      <Panel title="Method notes">
        {m.data.mainnet_replay === null && <p className="mb-2 text-fog-300">Mainnet replay: phase 2</p>}
        <ul className="list-disc space-y-1 pl-5 text-fog-300">{m.data.notes.map((x) => <li key={x}>{x}</li>)}</ul>
        <p className="mt-3 font-mono text-xs text-fog-500">rules {m.data.rules_version.slice(0, 19)}…</p>
      </Panel>
    </div>
  )
}
