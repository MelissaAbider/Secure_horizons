import { useState } from 'react'
import { api, ApiError, isNoSnapshotYet } from '../api'
import { ErrorText, Pill, SeverityBadge, TxLink, Waiting } from '../components/ui'
import { getOperator, useDashboardData } from '../DataContext'
import { formatUnits, formatUsd, formatUtc } from '../lib/format'
import { actionLabel, deploymentLabel, ruleLabel } from '../lib/labels'
import type { Action, Alert, Decision, StateResponse } from '../types'

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'neutral' | 'violet'> = {
  executed: 'ok', approved: 'ok', pending_approval: 'warn', planned: 'neutral', skipped: 'neutral', failed: 'bad', rejected: 'bad',
}

function decimalsFor(state: StateResponse | undefined, asset: string | undefined): number {
  if (!asset) return 18
  return state?.tokens.find((t) => t.symbol === asset)?.decimals ?? state?.reserves.find((r) => r.asset === asset)?.decimals ?? (asset === 'USDC' ? 6 : 18)
}

export function AlertCard({ a }: { a: Alert }) {
  return (
    <article data-testid="alert-card" className="rounded-xl border border-ink-700 bg-ink-850 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SeverityBadge severity={a.severity} />
        <span className="text-xs font-semibold uppercase tracking-wider text-fog-400">Alert · {ruleLabel(a.rule_id)}</span>
        <span className="ml-auto font-mono text-xs text-fog-500">block {a.block_number} · {formatUtc(a.block_time)}</span>
      </div>
      <h3 className="mt-2 text-lg font-semibold">{a.title}</h3>
      <p className="mt-1 text-fog-300">{a.explanation}</p>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-fog-400">
        <span>{deploymentLabel(a.deployment_id)}{a.asset ? ` · ${a.asset}` : ''}</span>
        <span>Exposure <span className="font-semibold tabular-nums text-fog-100">{formatUsd(a.exposure_usd)}</span></span>
      </div>
    </article>
  )
}

function ActionRow({ d, a, i, state, onDone }: { d: Decision; a: Action; i: number; state?: StateResponse; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string>()
  const asset = typeof a.params.asset === 'string' ? a.params.asset : undefined
  const dep = typeof a.params.deployment_id === 'string' ? a.params.deployment_id : undefined
  async function decide(approve: boolean) {
    setBusy(true); setErr(undefined)
    try {
      await api.approve(d.id, { action_index: i, approver: getOperator(), approve })
      onDone()
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e))
      if (e instanceof ApiError && e.status === 409) onDone()
    } finally { setBusy(false) }
  }
  return (
    <tr className="border-t border-ink-700 align-top">
      <td className="py-2.5 pr-3">
        <div className="font-medium">{actionLabel(a.type)}</div>
        {(dep || asset) && <div className="text-xs text-fog-400">{dep}{asset ? ` · ${asset}` : ''}</div>}
        {a.note && <div className="text-xs text-fog-500">{a.note}</div>}
      </td>
      <td className="py-2.5 pr-3"><Pill tone={a.mode === 'auto' ? 'violet' : 'warn'}>{a.mode === 'auto' ? 'AUTO' : 'HUMAN'}</Pill></td>
      <td className="py-2.5 pr-3"><Pill tone={STATUS_TONE[a.status] ?? 'neutral'}>{a.status.replace('_', ' ')}</Pill></td>
      <td className="py-2.5 pr-3 tabular-nums">{a.amount ? `${formatUnits(a.amount, decimalsFor(state, asset))} ${asset ?? ''}` : '—'}</td>
      <td className="py-2.5 pr-3"><TxLink hash={a.tx_hash} network={state?.network ?? d.network} /></td>
      <td className="py-2.5">
        {a.status === 'pending_approval' && (
          <div className="flex gap-2">
            <button data-testid={`approve-${d.id}-${i}`} disabled={busy} onClick={() => decide(true)}
              className="rounded-full bg-navy px-4 py-1.5 text-sm font-semibold text-white hover:bg-navy-soft disabled:opacity-50">Approve</button>
            <button data-testid={`reject-${d.id}-${i}`} disabled={busy} onClick={() => decide(false)}
              className="rounded-full border border-red-200 px-4 py-1.5 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50">Reject</button>
          </div>
        )}
        {err && <ErrorText>{err}</ErrorText>}
      </td>
    </tr>
  )
}

export function DecisionCard({ d, state, onDone }: { d: Decision; state?: StateResponse; onDone: () => void }) {
  return (
    <article data-testid="decision-card" className="rounded-xl border border-blue-200 bg-ink-850 p-5  ring-1 ring-blue-200">
      <div className="flex flex-wrap items-center gap-3">
        <SeverityBadge severity={d.severity} />
        <span className="text-xs font-semibold uppercase tracking-wider text-blue-700">Decision</span><span className="font-mono text-xs text-blue-700">{d.id}</span>
        <span className="ml-auto font-mono text-xs text-fog-500">block {d.block_number}</span>
      </div>
      <p className="mt-2 text-fog-100">{d.rationale}</p>
      <div className="mt-2 flex flex-wrap gap-x-6 text-sm text-fog-400">
        <span>Exposure <span className="font-semibold text-fog-100">{formatUsd(d.exposure_usd)}</span></span>
        <span>Withdrawable <span className="font-semibold text-fog-100">{formatUsd(d.withdrawable_usd)}</span></span>
        <span className="font-mono text-xs">{d.matrix_cell}</span>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="text-xs uppercase tracking-wider text-fog-400">
            <tr><th className="pb-2 pr-3">Action</th><th className="pb-2 pr-3">Mode</th><th className="pb-2 pr-3">Status</th><th className="pb-2 pr-3">Amount</th><th className="pb-2 pr-3">Transaction</th><th className="pb-2" /></tr>
          </thead>
          <tbody>{d.actions.map((a, i) => <ActionRow key={i} d={d} a={a} i={i} state={state} onDone={onDone} />)}</tbody>
        </table>
      </div>
    </article>
  )
}

type Item = { kind: 'alert'; block: number; a: Alert } | { kind: 'decision'; block: number; d: Decision }

export function Alerts() {
  const { state, alerts, decisions } = useDashboardData()
  if (!state.data && !alerts.data && isNoSnapshotYet(state.error)) return <Waiting />
  const items: Item[] = [
    ...(alerts.data ?? []).map((a) => ({ kind: 'alert' as const, block: a.block_number, a })),
    ...(decisions.data ?? []).map((d) => ({ kind: 'decision' as const, block: d.block_number, d })),
  ].sort((x, y) => y.block - x.block || (x.kind === 'decision' ? -1 : 1) - (y.kind === 'decision' ? -1 : 1))

  if (items.length === 0) return <p className="text-fog-400">No alert so far. The platform is watching.</p>
  return (
    <div className="space-y-4">
      {items.map((it) => it.kind === 'alert'
        ? <AlertCard key={it.a.id} a={it.a} />
        : <DecisionCard key={it.d.id} d={it.d} state={state.data} onDone={() => { void decisions.refresh() }} />)}
    </div>
  )
}
