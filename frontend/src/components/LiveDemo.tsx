import { useState, type ReactNode } from 'react'
import { api, ApiError } from '../api'
import { useDashboardData } from '../DataContext'
import { usePolling } from '../hooks/usePolling'
import { formatUsd, formatUtc, shortHash } from '../lib/format'
import { ruleLabel } from '../lib/labels'
import type { DemoRun, DemoStep } from '../types'
import { Pill, SeverityBadge } from './ui'

// Live part of the setup page, shown once monitoring is on: launch the attack on Fuji, follow it on chain and in
// our monitor, then get the DORA draft and the Discord confirmation. Everything comes from the backend.

const RUN_KEY = 'sh.liveRun'
const STEP_LABELS: Record<string, string> = {
  start: 'Attack starts',
  forged_mint: 'Forged rsETH release (no WETH locked)',
  collateral_deposit: 'Unbacked rsETH posted as collateral',
  borrow: 'Borrow against the fake collateral',
  bot_withdraw: 'A lender tries to get out',
  liquidity_zero: 'WETH market drained',
  protocol_freeze: 'Protocol guardian freezes rsETH',
  done: 'Run finished',
  preflight: 'Pre-flight check',
  error: 'Run stopped',
}
const PHASES = [
  { step: 'forged_mint', label: 'Forged release' },
  { step: 'collateral_deposit', label: 'Fake collateral' },
  { step: 'liquidity_zero', label: 'Market drained' },
  { step: 'protocol_freeze', label: 'Protocol freeze' },
]
const CARD = 'rounded-2xl border border-ink-700 bg-white p-5'
const BTN = 'inline-flex items-center justify-center gap-2 rounded-2xl bg-fog-100 px-5 py-3 text-[15px] font-semibold text-ink-950 transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40'
const BTN_LIGHT = 'inline-flex items-center justify-center gap-2 rounded-2xl border border-ink-700 bg-white px-5 py-3 text-[15px] font-semibold text-fog-100 transition hover:border-fog-500 disabled:cursor-not-allowed disabled:opacity-40'

function loadRunId(): string | undefined { try { return localStorage.getItem(RUN_KEY) ?? undefined } catch { return undefined } }
function saveRunId(id: string): void { try { localStorage.setItem(RUN_KEY, id) } catch { /* storage unavailable */ } }

function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="font-mono text-[12px] font-medium uppercase tracking-[0.24em] text-fog-400">{children}</div>
}

function TxLink({ explorer, hash }: { explorer?: string; hash: string | null }) {
  if (!hash) return <span className="text-fog-500">—</span>
  if (!explorer) return <span className="font-mono">{shortHash(hash)}</span>
  return <a href={`${explorer}/tx/${hash}`} target="_blank" rel="noreferrer" className="font-mono text-signal-violet hover:underline">{shortHash(hash)} ↗</a>
}

function BlockLink({ explorer, block }: { explorer?: string; block: number | null }) {
  if (block === null) return <span className="text-fog-500">—</span>
  const text = block.toLocaleString('en-US')
  return explorer
    ? <a href={`${explorer}/block/${block}`} target="_blank" rel="noreferrer" className="tabular-nums hover:underline">{text}</a>
    : <span className="tabular-nums">{text}</span>
}

function stepTone(s: DemoStep): 'ok' | 'warn' | 'bad' | 'neutral' {
  return s.status === 'ok' ? 'ok' : s.status === 'blocked' ? 'warn' : s.status === 'failed' ? 'bad' : 'neutral'
}

export function LiveDemo() {
  const { health, state, alerts } = useDashboardData()
  const config = usePolling(() => api.notificationsConfig(), 15000)
  const [runId, setRunId] = useState<string | undefined>(loadRunId)
  const [first, setFirst] = useState<DemoRun>()
  const [msg, setMsg] = useState<string>()
  const run = usePolling(async () => (runId ? api.demoRun(runId) : undefined), 2000, [runId])
  const incidents = usePolling(() => api.incidents(), 3000)
  const deliveries = usePolling(() => api.notifications(), 3000)

  const lost = run.error instanceof ApiError && run.error.status === 404  // backend restarted since that run
  const current = lost ? undefined : run.data ?? first
  const running = current?.status === 'running'
  const explorer = config.data?.network === 'fuji' ? config.data.explorer_url : undefined
  const attack = current?.kind === 'attack' ? current : undefined
  const steps = (attack?.steps ?? []).filter((s) => s.step in STEP_LABELS)
  const reached = new Set(steps.filter((s) => s.status !== 'failed').map((s) => s.step))
  const startBlock = attack?.steps.find((s) => s.step === 'start')?.block ?? undefined
  const forgedBlock = attack?.steps.find((s) => s.step === 'forged_mint')?.block ?? undefined
  const startedAt = attack ? Date.parse(attack.started_at) - 5000 : undefined
  const detected = startBlock === undefined ? [] : (alerts.data ?? [])
    .filter((a) => a.block_number >= startBlock).sort((a, b) => a.block_number - b.block_number)
  const incident = startedAt === undefined ? undefined
    : (incidents.data ?? []).find((i) => Date.parse(i.opened_at) >= startedAt)
  const sent = startedAt === undefined ? [] : (deliveries.data ?? []).filter((d) => Date.parse(d.at) >= startedAt).reverse()
  const failure = current?.status === 'failed' ? [...current.steps].reverse().find((s) => s.status === 'failed') : undefined
  const h = health.data

  async function start(call: () => Promise<DemoRun>) {
    setMsg(undefined)
    try { const r = await call(); setFirst(r); setRunId(r.run_id); saveRunId(r.run_id) }
    catch (e) { setMsg(e instanceof ApiError ? e.detail : String(e)) }
  }
  function reset() {
    if (window.confirm('Redeploy every contract on the test network and seed them again? A few minutes; addresses change.')) {
      void start(() => api.demoReset())
    }
  }

  return (
    <section data-testid="live-demo" className="mt-6 rounded-[28px] border border-white bg-white/75 p-7 shadow-[0_20px_60px_-30px_rgba(21,27,46,.25)] backdrop-blur sm:p-9">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <Eyebrow>Live monitoring</Eyebrow>
          <h2 className="mt-3 font-display text-[26px] font-semibold tracking-[-0.02em]">Your positions are under watch</h2>
          <p data-testid="monitor-status" className="mt-2 flex items-center gap-2 text-[15px] text-fog-400">
            <span className={`h-2.5 w-2.5 rounded-full ${h?.engine_running && h.rpc_ok ? 'pulse-dot bg-green-500' : 'bg-amber-500'}`} />
            {!h ? 'Connecting to the monitor…'
              : !h.engine_running ? 'Monitor engine off: start the backend with ENGINE_ENABLED=true'
              : `Watching ${h.network === 'fuji' ? 'Avalanche Fuji' : h.network} · block ${h.block_number.toLocaleString('en-US')}`}
            {state.data && ` · ${state.data.positions.length} positions, ${formatUsd(state.data.totals.value_usd)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button data-testid="launch-attack" disabled={running} onClick={() => void start(() => api.demoAttack(0, 'default'))} className={BTN}>
            {running && attack ? 'Attack in progress…' : 'Launch the attack on Fuji'} <span aria-hidden>→</span>
          </button>
          <button data-testid="reset-demo" disabled={running} onClick={reset} className={BTN_LIGHT}>Reset the test network</button>
        </div>
      </div>

      {msg && <p role="alert" className="mt-4 text-[14px] text-rose-glow">{msg}</p>}
      {failure && (
        <p role="alert" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[14px] text-amber-800">
          {failure.msg}{failure.msg.includes('make reset') && ' Use “Reset the test network”, then launch again.'}
        </p>
      )}
      {current?.kind === 'reset' && (
        <div className={`${CARD} mt-6`} data-testid="reset-run">
          <div className="flex items-center justify-between"><b>Resetting the test network</b><Pill tone={current.status === 'done' ? 'ok' : current.status === 'failed' ? 'bad' : 'warn'}>{current.status}</Pill></div>
          <pre className="mt-3 max-h-40 overflow-auto font-mono text-[12px] text-fog-400">{current.log.slice(-6).join('\n') || '…'}</pre>
        </div>
      )}

      {attack && (
        <>
          <ol className="mt-7 grid gap-2 sm:grid-cols-4" data-testid="phases">
            {PHASES.map((p, i) => (
              <li key={p.step} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-[14px] ${reached.has(p.step) ? 'border-red-200 bg-red-50 text-red-700' : 'border-ink-700 bg-white text-fog-400'}`}>
                <span className="font-mono text-[12px]">{reached.has(p.step) ? '●' : i + 1}</span>{p.label}
              </li>
            ))}
          </ol>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className={CARD}>
              <div className="flex items-center justify-between">
                <b>On chain: the attack</b>
                <Pill tone={attack.status === 'done' ? 'ok' : attack.status === 'failed' ? 'bad' : 'warn'}>{attack.status}</Pill>
              </div>
              <table className="mt-3 w-full text-left text-[13px]" data-testid="attack-steps">
                <thead className="font-mono text-[10px] uppercase tracking-[0.14em] text-fog-500">
                  <tr><th className="py-2 pr-2">Step</th><th className="pr-2">Block</th><th className="pr-2">Status</th><th>Transaction</th></tr>
                </thead>
                <tbody>
                  {steps.length === 0 && <tr><td colSpan={4} className="py-3 text-fog-400">Waiting for the first transaction…</td></tr>}
                  {steps.map((s, i) => (
                    <tr key={i} className="border-t border-ink-700 align-top">
                      <td className="py-2 pr-2"><div className="font-medium">{STEP_LABELS[s.step]}</div><div className="text-[12px] text-fog-400">{s.step === 'done' ? 'Ground truth of the run saved by the scenario' : s.msg}</div></td>
                      <td className="py-2 pr-2"><BlockLink explorer={explorer} block={s.block} /></td>
                      <td className="py-2 pr-2"><Pill tone={stepTone(s)}>{s.status}</Pill></td>
                      <td className="py-2"><TxLink explorer={explorer} hash={s.tx_hash} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={CARD}>
              <div className="flex items-center justify-between"><b>Our monitor</b><span className="text-[13px] text-fog-400">{detected.length} alert{detected.length === 1 ? '' : 's'}</span></div>
              <table className="mt-3 w-full text-left text-[13px]" data-testid="detections">
                <thead className="font-mono text-[10px] uppercase tracking-[0.14em] text-fog-500">
                  <tr><th className="py-2 pr-2">Rule</th><th className="pr-2">Severity</th><th className="pr-2">Block</th><th>After the forged release</th></tr>
                </thead>
                <tbody>
                  {detected.length === 0 && <tr><td colSpan={4} className="py-3 text-fog-400">Nothing abnormal yet.</td></tr>}
                  {detected.map((a) => (
                    <tr key={a.id} className="border-t border-ink-700 align-top">
                      <td className="py-2 pr-2"><div className="font-medium">{ruleLabel(a.rule_id)}</div><div className="text-[12px] text-fog-400">{a.explanation}</div></td>
                      <td className="py-2 pr-2"><SeverityBadge severity={a.severity} /></td>
                      <td className="py-2 pr-2"><BlockLink explorer={explorer} block={a.block_number} /></td>
                      <td className="py-2 tabular-nums">{forgedBlock === undefined ? '—' : `+${a.block_number - forgedBlock} blocks`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className={CARD} data-testid="dora-card">
              <div className="flex items-center justify-between"><b>DORA initial notification</b>
                {incident?.dora && <Pill tone={incident.dora.is_major ? 'bad' : 'ok'}>{incident.dora.is_major ? 'major incident' : 'not major'}</Pill>}
              </div>
              {!incident?.dora ? <p className="mt-3 text-fog-400">The draft is written as soon as a critical alert opens an incident.</p> : (
                <>
                  <dl className="mt-3 divide-y divide-ink-700 text-[14px]">
                    {[
                      ['Incident', <span className="font-mono">{incident.id}</span>],
                      ['Classification', `${incident.dora.thresholds_met.map((t) => t.split(' ')[0]).join(', ') || 'no threshold'} met`],
                      ['Exposure at detection', formatUsd(incident.exposure_usd)],
                      ['Detected', formatUtc(incident.detected_at)],
                      ['Initial notification due', formatUtc(incident.dora.deadlines.initial_notification_due)],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="flex justify-between gap-4 py-2"><dt className="text-fog-400">{k}</dt><dd className="text-right font-medium">{v}</dd></div>
                    ))}
                  </dl>
                  <a data-testid="download-dora" href={api.incidentPdfUrl(incident.id)} download className={`${BTN} mt-4 w-full`}>Download the DORA PDF</a>
                  <p className="mt-2 text-[12px] text-fog-400">Draft only: an authorised person reviews and submits it.</p>
                </>
              )}
            </div>

            <div className={CARD} data-testid="discord-card">
              <div className="flex items-center justify-between"><b>Discord alerts</b>
                {config.data && <Pill tone={config.data.discord_configured ? 'ok' : 'warn'}>{config.data.discord_configured ? 'webhook set' : 'webhook missing'}</Pill>}
              </div>
              {config.data && !config.data.discord_configured && (
                <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
                  No Discord webhook yet: add ALERT_WEBHOOK_URL to .env and restart the backend. The alerts below were prepared but not sent.
                </p>
              )}
              <ul className="mt-3 divide-y divide-ink-700 text-[14px]">
                {sent.length === 0 && <li className="py-2 text-fog-400">No alert to send yet.</li>}
                {sent.map((d, i) => (
                  <li key={i} className="flex items-start justify-between gap-3 py-2">
                    <div>
                      <div className="font-medium">{d.rule_ids.map(ruleLabel).join(', ')}</div>
                      <div className="text-[12px] text-fog-400">{formatUtc(d.at)}{d.attachment && ` · ${d.attachment} attached`}</div>
                    </div>
                    <Pill tone={d.status === 'sent' ? 'ok' : d.status === 'failed' ? 'bad' : 'warn'}>
                      {d.status === 'sent' ? 'sent ✓' : d.status === 'failed' ? `failed${d.http_status ? ` ${d.http_status}` : ''}` : 'not sent'}
                    </Pill>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
