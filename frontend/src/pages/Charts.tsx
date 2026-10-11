import { useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, isNoSnapshotYet } from '../api'
import { Panel, SeverityBadge, Waiting } from '../components/ui'
import { useDashboardData } from '../DataContext'
import { usePolling } from '../hooks/usePolling'
import { alertsForReserve, toChartPoints, type ChartPoint } from '../lib/chart'
import { formatUtc } from '../lib/format'
import { deploymentLabel, ruleShort } from '../lib/labels'
import type { Alert } from '../types'

const SEV_COLOR: Record<string, string> = { info: '#64748b', warning: '#f59e0b', high: '#ea580c', critical: '#dc2626' }

interface ChartSpec {
  id: string; title: string; key: keyof ChartPoint; unit: string; color: string
  thresholds?: { y: number; label: string }[]; domain?: [number, number]; note?: string
}

const CHARTS: ChartSpec[] = [
  { id: 'chart-utilization', title: 'Utilization', key: 'utilization', unit: '%', color: '#19A7FF', domain: [0, 100], thresholds: [{ y: 90, label: '90% warning' }, { y: 98, label: '98% critical' }] },
  { id: 'chart-liquidity', title: 'Available liquidity', key: 'liquidity', unit: '', color: '#F1F3F7' },
  { id: 'chart-withdrawable', title: 'Our position: withdrawable', key: 'withdrawable', unit: '%', color: '#4ade80', domain: [0, 100], thresholds: [{ y: 80, label: '80% high' }, { y: 50, label: '50% critical' }] },
  { id: 'chart-apy', title: 'Supply APY', key: 'apy', unit: '%', color: '#f472b6' },
  { id: 'chart-backing', title: 'rsETH backing', key: 'backing', unit: '%', color: '#fbbf24', domain: [0, 100], thresholds: [{ y: 99, label: '99% R1' }] },
]

function SeriesChart({ spec, data, markers, asset }: { spec: ChartSpec; data: ChartPoint[]; markers: Alert[]; asset: string }) {
  return (
    <Panel title={spec.title} testId={spec.id}>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 22, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#161C28" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="block" domain={['dataMin', 'dataMax']} tick={{ fill: '#7A8396', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} tickFormatter={(b: number) => String(b).slice(-4)} />
            <YAxis domain={spec.domain ?? ['auto', 'auto']} tick={{ fill: '#7A8396', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} width={56} tickFormatter={(v: number) => `${Math.round(v)}${spec.unit}`} />
            <Tooltip contentStyle={{ background: '#0B0F17', border: '1px solid #2A3242', borderRadius: 8, fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }} labelFormatter={(b) => `Block ${b}`}
              formatter={(v) => [typeof v === 'number' ? `${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}${spec.unit}` : '—', spec.title]} />
            {spec.thresholds?.map((t) => (
              <ReferenceLine key={t.y} y={t.y} stroke="#3A4356" strokeDasharray="4 4" label={{ value: t.label, fill: '#7A8396', fontSize: 11, position: 'insideTopRight' }} />
            ))}
            {markers.map((a) => (
              <ReferenceLine key={a.id} x={a.block_number} className="alert-marker" stroke={SEV_COLOR[a.severity]} strokeWidth={2}
                strokeDasharray={a.asset === asset ? undefined : '5 4'}
                label={{ value: ruleShort(a.rule_id), fill: SEV_COLOR[a.severity], fontSize: 12, fontWeight: 700, position: 'top' }} />
            ))}
            <Line type="linear" dataKey={spec.key} stroke={spec.color} strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {spec.note && <p className="mt-2 text-xs text-fog-500">{spec.note}</p>}
    </Panel>
  )
}

export function Charts() {
  const { state, alerts } = useDashboardData()
  const [params, setParams] = useSearchParams()
  const reserve = params.get('reserve') ?? 'lend-eth:WETH'
  const [dep, asset] = reserve.split(':')
  const series = usePolling(() => api.series(dep, asset, 300), 2000, [reserve])

  if (!state.data && isNoSnapshotYet(state.error)) return <Waiting />
  const options = (state.data?.reserves ?? []).filter((r) => r.borrowable)
  const decimals = state.data?.reserves.find((r) => r.deployment_id === dep && r.asset === asset)?.decimals ?? 18
  const pts = series.data ?? []
  const data = toChartPoints(pts, decimals)
  const minB = pts[0]?.block_number ?? 0
  const maxB = pts[pts.length - 1]?.block_number ?? 0
  const markers = alertsForReserve(alerts.data ?? [], dep, asset, minB, maxB)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="reserve" className="text-sm font-semibold text-fog-300">Market</label>
        <select id="reserve" value={reserve} onChange={(e) => setParams({ reserve: e.target.value })}
          className="rounded-full border border-ink-700 bg-ink-850 px-4 py-2 text-fog-100">
          {(options.length ? options : [{ deployment_id: dep, asset }]).map((r) => (
            <option key={`${r.deployment_id}:${r.asset}`} value={`${r.deployment_id}:${r.asset}`}>{deploymentLabel(r.deployment_id)} · {r.asset}</option>
          ))}
        </select>
        <span className="text-sm text-fog-500">{pts.length} points · blocks {minB}–{maxB}</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {CHARTS.map((c) => <SeriesChart key={c.id} spec={c} data={data} markers={markers} asset={asset} />)}
      </div>
      <Panel title="Events on this chart">
        {markers.length === 0 ? <p className="text-fog-400">No alert in this window.</p> : (
          <ul className="space-y-2">
            {markers.map((a) => (
              <li data-testid="alert-marker-item" key={a.id} className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-sm text-fog-400">#{a.block_number}</span>
                <SeverityBadge severity={a.severity} />
                <span className="font-semibold">{ruleShort(a.rule_id)}</span>
                <span className="text-fog-300">{a.title}</span>
                <span className="text-xs text-fog-500">{formatUtc(a.block_time)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}
