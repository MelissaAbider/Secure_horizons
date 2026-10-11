import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, ApiError } from '../api'
import { ErrorText, Panel, Pill, SeverityBadge, Stat, TxLink } from '../components/ui'
import { getOperator, useDashboardData } from '../DataContext'
import { useNow } from '../hooks/useNow'
import { usePolling } from '../hooks/usePolling'
import { formatCountdown, formatUsd, formatUtc } from '../lib/format'
import type { DoraCriteria, Incident } from '../types'

type Row = [keyof DoraCriteria, string, string, (v: unknown) => string]
const pct = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(1)}%` : '—')
const num = (v: unknown) => (typeof v === 'number' ? v.toLocaleString('en-US') : '—')
const yes = (v: unknown) => (typeof v === 'boolean' ? (v ? 'Yes' : 'No') : '—')
const hrs = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(2)} h` : '—')
const eur = (v: unknown) => (typeof v === 'number' ? `€${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—')

export const CRITERIA_ROWS: Row[] = [
  ['critical_services_affected', 'Critical services affected', 'required for "major" (Art. 8(1))', yes],
  ['clients_affected_pct', 'Clients affected', '> 10% (Art. 9(1))', pct],
  ['clients_affected_count', 'Clients affected (count)', '> 100,000 (Art. 9(1))', num],
  ['counterparts_affected_pct', 'Financial counterparts affected', '> 30% (Art. 9(1))', pct],
  ['transactions_affected_value_pct', 'Transactions affected (value)', '> 10% (Art. 9(1))', pct],
  ['transactions_affected_count_pct', 'Transactions affected (count)', '> 10% (Art. 9(1))', pct],
  ['relevant_clients_affected', 'Relevant clients or counterparts affected', 'any (Art. 9(1))', yes],
  ['reputational_impact', 'Reputational impact', 'any (Art. 9(2))', yes],
  ['duration_hours', 'Incident duration', '> 24 h (Art. 9(3))', hrs],
  ['critical_service_downtime_hours', 'Critical service downtime', '> 2 h (Art. 9(3))', hrs],
  ['member_states_affected', 'EU member states affected', '≥ 2 (Art. 9(4))', num],
  ['data_losses', 'Data losses', 'any (Art. 9(5)(a))', yes],
  ['malicious_unauthorised_access', 'Malicious unauthorised access', 'any (Art. 9(5)(b))', yes],
  ['economic_impact_eur', 'Economic impact', '> €100,000 (Art. 9(6))', eur],
]

const STATUS_TONE = { open: 'bad', contained: 'warn', resolved: 'ok' } as const

function Deadline({ id, label, due, now }: { id: string; label: string; due: string; now: number }) {
  const over = Date.parse(due) < now
  return (
    <div data-testid={id} className={`rounded-lg border p-4 ${over ? 'border-red-200 bg-red-50' : 'border-ink-700 bg-ink-900'}`}>
      <div className="text-xs font-semibold uppercase tracking-wider text-fog-400">{label}</div>
      <div className="mt-1 font-mono text-sm text-fog-100">{formatUtc(due)}</div>
      <div className={`mt-1 text-lg font-bold ${over ? 'text-red-600' : 'text-fog-100'}`}>{formatCountdown(due, now)}</div>
    </div>
  )
}

export function IncidentView({ inc, onChange }: { inc: Incident; onChange: () => void }) {
  const now = useNow(1000)
  const { state } = useDashboardData()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string>()
  const dora = inc.dora
  const ttc = inc.contained_at ? Math.round((Date.parse(inc.contained_at) - Date.parse(inc.detected_at)) / 1000) : null

  async function submit() {
    if (!window.confirm('Submit the DORA initial notification to the regulator?')) return
    setBusy(true); setErr(undefined)
    try { await api.submitIncident(inc.id, getOperator()); onChange() }
    catch (e) { setErr(e instanceof ApiError ? e.detail : String(e)) }
    finally { setBusy(false) }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-ink-700 bg-ink-850 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <SeverityBadge severity={inc.severity} />
          <Pill tone={STATUS_TONE[inc.status]}>{inc.status.toUpperCase()}</Pill>
          <span className="font-mono text-sm text-fog-400">{inc.id}</span>
        </div>
        <h1 className="mt-2 text-2xl font-bold">{inc.title}</h1>
        
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Saved" value={formatUsd(inc.saved_usd)} accent="ok" />
        <Stat label="Still at risk" value={formatUsd(inc.at_risk_usd)} accent={inc.at_risk_usd > 0 ? 'bad' : 'neutral'} />
        <Stat label="Time to contain" value={ttc === null ? '—' : `${ttc} s`} />
      </div>

      <Panel title="Timeline">
        <ol className="relative space-y-3 border-l border-ink-600 pl-5">
          {[...inc.timeline].sort((a, b) => a.at.localeCompare(b.at) || (a.block_number ?? 0) - (b.block_number ?? 0)).map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full bg-signal-violet" />
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-xs text-fog-400">{formatUtc(e.at).slice(11)}</span>
                {e.block_number !== null && <span className="font-mono text-xs text-fog-500">#{e.block_number}</span>}
                <Pill tone={e.kind === 'alert' ? 'bad' : e.kind === 'human' ? 'warn' : e.kind === 'action' ? 'ok' : e.kind === 'dora' ? 'violet' : 'neutral'}>{e.kind}</Pill>
                <span className="text-fog-100">{e.text}</span>
                {e.ref?.startsWith('0x') && <TxLink hash={e.ref} network={state.data?.network} />}
              </div>
            </li>
          ))}
        </ol>
      </Panel>

      {dora && (
        <>
          <Panel title="DORA classification" right={dora.is_major ? <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-black tracking-wide text-white">MAJOR INCIDENT</span> : <Pill>NOT MAJOR</Pill>}>
            <p className="text-fog-100">{dora.legal_basis}</p>
            <div className="mt-3 flex flex-wrap gap-2">{dora.thresholds_met.map((t) => <Pill key={t} tone="violet">{t}</Pill>)}</div>
            <details className="group mt-4">
              <summary className="cursor-pointer list-none font-mono text-[12px] uppercase tracking-[0.2em] text-fog-500"><span className="group-open:hidden">14 criteria · show +</span><span className="hidden group-open:inline">hide −</span></summary>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wider text-fog-400"><tr><th className="pb-2 pr-3">Criterion</th><th className="pb-2 pr-3">Value</th><th className="pb-2">Threshold (RTS 2024/1772)</th></tr></thead>
                <tbody>
                  {CRITERIA_ROWS.map(([k, label, thr, fmt]) => (
                    <tr key={k} className="border-t border-ink-700">
                      <td className="py-2 pr-3">{label}</td>
                      <td className="py-2 pr-3 font-semibold tabular-nums">{k in dora.criteria ? fmt(dora.criteria[k]) : '—'}</td>
                      <td className="py-2 text-fog-400">{thr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </details>
          </Panel>

          <div className="grid gap-4 md:grid-cols-3">
            <Deadline id="deadline-initial" label="Initial notification" due={dora.deadlines.initial_notification_due} now={now} />
            <Deadline id="deadline-intermediate" label="Intermediate report" due={dora.deadlines.intermediate_report_due} now={now} />
            <Deadline id="deadline-final" label="Final report" due={dora.deadlines.final_report_due} now={now} />
          </div>

          <Panel title="DORA report (draft)" right={
            dora.submitted
              ? <span className="text-sm text-green-700">Submitted by {dora.submitted_by} at {formatUtc(dora.submitted_at)}</span>
              : <button data-testid="submit-incident" disabled={busy} onClick={submit}
                  className="rounded-full bg-navy px-5 py-2.5 text-sm font-semibold uppercase tracking-wide text-white hover:bg-navy-soft disabled:opacity-50">Submit to regulator</button>
          }>
            {dora.ai_drafted_sections.length > 0 && (
              <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">
                AI-drafted sections, human review required: {dora.ai_drafted_sections.join(', ')}
              </div>
            )}
            <details className="group">
              <summary className="cursor-pointer list-none font-mono text-[12px] uppercase tracking-[0.2em] text-fog-500"><span className="group-open:hidden">Read the pre-filled report +</span><span className="hidden group-open:inline">hide −</span></summary>
              <div className="report mt-4"><ReactMarkdown remarkPlugins={[remarkGfm]}>{dora.report_markdown}</ReactMarkdown></div>
            </details>
            {err && <ErrorText>{err}</ErrorText>}
          </Panel>
        </>
      )}
    </div>
  )
}

export function IncidentPage() {
  const { state } = useDashboardData()
  const list = usePolling(() => api.incidents(), 2000)
  const incs = list.data ?? []
  const inc = incs.find((i) => i.id === state.data?.open_incident_id)
    ?? [...incs].sort((a, b) => b.opened_at.localeCompare(a.opened_at))[0]
  if (!list.data) return list.error ? <p className="text-red-600">Could not load incidents: {list.error.message}</p> : <p className="text-fog-400">Loading…</p>
  if (!inc) return <p className="text-fog-300">No incident so far.</p>
  return <IncidentView inc={inc} onChange={() => { void list.refresh() }} />
}
