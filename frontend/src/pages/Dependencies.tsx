import { api } from '../api'
import { Panel, Pill } from '../components/ui'
import { usePolling } from '../hooks/usePolling'

const RANK = { critical: 0, important: 1, standard: 2 } as const
const DOT = { ok: 'bg-green-500', degraded: 'bg-amber-500', down: 'bg-red-500', unknown: 'bg-slate-500' } as const

export function Dependencies() {
  const deps = usePolling(() => api.dependencies(), 30000)
  const rows = [...(deps.data ?? [])].sort((a, b) => (RANK[a.criticality] ?? 9) - (RANK[b.criticality] ?? 9))
  return (
    <Panel title="Third-party register (DORA Art. 28)">
      {deps.error && <p className="text-red-600">Could not load dependencies: {deps.error.message}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-[15px]">
          <thead className="text-xs uppercase tracking-wider text-fog-400">
            <tr><th className="pb-2 pr-3">Name</th><th className="pb-2 pr-3">Kind</th><th className="pb-2 pr-3">Provider</th><th className="pb-2 pr-3">Criticality</th><th className="pb-2 pr-3">Supports</th><th className="pb-2 pr-3">Fallback</th><th className="pb-2">Status</th></tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id} className="border-t border-ink-700">
                <td className="py-3 pr-3 font-semibold">{d.name}</td>
                <td className="py-3 pr-3 text-fog-300">{d.kind}</td>
                <td className="py-3 pr-3 text-fog-300">{d.provider}</td>
                <td className="py-3 pr-3"><Pill tone={d.criticality === 'critical' ? 'bad' : d.criticality === 'important' ? 'warn' : 'neutral'}>{d.criticality}</Pill></td>
                <td className="py-3 pr-3"><div className="flex flex-wrap gap-1">{d.supports.map((s) => <Pill key={s}>{s}</Pill>)}</div></td>
                <td className="py-3 pr-3 text-sm text-fog-300">{d.fallback ?? '—'}</td>
                <td className="py-3"><span className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${DOT[d.status] ?? 'bg-slate-500'}`} />{d.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
