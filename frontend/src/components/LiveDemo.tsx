import { useState, type ReactNode } from 'react'
import { api, ApiError } from '../api'
import { useDashboardData } from '../DataContext'
import { usePolling } from '../hooks/usePolling'
import { formatUsd, formatUtc, severityClass, shortHash } from '../lib/format'
import { ruleLabel } from '../lib/labels'
import type { DemoRun, DemoStep, DiscordAction } from '../types'
import { ChannelLogo } from './ChannelLogo'
import { Pill } from './ui'

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

function Severity({ severity }: { severity: string }) {
  return (
    <span className={`inline-flex w-[84px] justify-center rounded px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-[0.12em] text-white ${severityClass[severity] ?? 'bg-slate-600'}`}>
      {severity}
    </span>
  )
}

function stepTone(s: DemoStep): 'ok' | 'warn' | 'bad' | 'neutral' {
  return s.status === 'ok' ? 'ok' : s.status === 'blocked' ? 'warn' : s.status === 'failed' ? 'bad' : 'neutral'
}

const ACTION_TONE: Record<DiscordAction['status'], 'ok' | 'warn' | 'bad' | 'neutral'> = {
  executed: 'ok', simulated: 'ok', partial: 'warn', pending: 'neutral', failed: 'bad', refused: 'bad',
}

function DiscordActionRow({ action, explorer }: { action: DiscordAction; explorer?: string }) {
  return (
    <li className="rounded-xl border border-ink-700 p-3 text-[13px]" data-testid="discord-action">
      <div className="flex items-center justify-between gap-3">
        <b>{action.label}</b>
        <Pill tone={ACTION_TONE[action.status]}>{action.status === 'pending' ? 'in progress…' : action.status}</Pill>
      </div>
      <div className="mt-1 text-fog-400">{formatUtc(action.at)} · clicked by {action.user}{action.reason ? ` · ${action.reason}` : ''}</div>
      {action.results.map((r) => (
        <div key={r.integration} className="mt-1 flex flex-wrap items-center gap-2">
          <span className="font-mono">{r.integration}</span><span>{r.verdict}</span>
          {r.txs.map((t) => <TxLink key={t} explorer={explorer} hash={t} />)}
          {r.detail && <span className="text-fog-400">{r.detail}</span>}
        </div>
      ))}
    </li>
  )
}

function DetectionLayer({ index, name, id, detail, available, alerting }: {
  index: string; name: string; id: string; detail: string; available: boolean; alerting: boolean
}) {
  const label = !available ? 'Unavailable' : alerting ? 'Threat detected' : 'Monitoring'
  const dot = !available ? 'bg-slate-300' : alerting ? 'bg-amber-500 shadow-[0_0_0_6px_rgba(245,158,11,.12)]' : 'bg-emerald-500'
  return (
    <div className="relative flex min-w-0 flex-1 gap-4 px-1 py-3" data-layer={id}>
      <div className="flex flex-col items-center">
        <span className="font-mono text-[10px] font-semibold tracking-[0.16em] text-fog-500">{index}</span>
        <span className={`mt-3 h-2.5 w-2.5 rounded-full transition ${dot}`} />
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <b className="text-[15px] text-fog-100">{name}</b>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-fog-500">{id}</span>
        </div>
        <p className="mt-1 text-[12px] leading-5 text-fog-400">{detail}</p>
        <p className={`mt-2 text-[11px] font-semibold uppercase tracking-[0.12em] ${alerting ? 'text-amber-600' : available ? 'text-emerald-600' : 'text-slate-400'}`}>{label}</p>
      </div>
    </div>
  )
}

export function LiveDemo() {
  const { health, state, alerts, layers } = useDashboardData()
  const config = usePolling(() => api.notificationsConfig(), 15000)
  const [runId, setRunId] = useState<string | undefined>(loadRunId)
  const [first, setFirst] = useState<DemoRun>()
  const [msg, setMsg] = useState<string>()
  const run = usePolling(async () => (runId ? api.demoRun(runId) : undefined), 2000, [runId])
  const incidents = usePolling(() => api.incidents(), 3000)
  const deliveries = usePolling(() => api.notifications(), 3000)
  const discordActions = usePolling(() => api.discordActions(), 3000)

  const lost = run.error instanceof ApiError && run.error.status === 404  // backend restarted since that run
  const current = lost ? undefined : run.data ?? first
  const running = current?.status === 'running'
  const explorer = config.data?.network === 'fuji' ? config.data.explorer_url : undefined
  const attack = current?.kind === 'attack' ? current : undefined
  const steps = (attack?.steps ?? []).filter((s) => s.step in STEP_LABELS)
  const reached = new Set(steps.filter((s) => s.status !== 'failed').map((s) => s.step))
  const startBlock = attack?.steps.find((s) => s.step === 'start')?.block ?? undefined
  const startedAt = attack ? Date.parse(attack.started_at) - 5000 : undefined
  const detected = startBlock === undefined ? [] : (alerts.data ?? [])
    .filter((a) => a.block_number >= startBlock).sort((a, b) => a.block_number - b.block_number)
  const incident = startedAt === undefined ? undefined
    : (incidents.data ?? []).find((i) => Date.parse(i.opened_at) >= startedAt)
  // one summary alert per incident, sent as soon as the fraud is detected
  const summary = startedAt === undefined ? undefined : (deliveries.data ?? []).find((d) => Date.parse(d.at) >= startedAt && d.incident_id)
  const clicks = startedAt === undefined ? [] : (discordActions.data ?? []).filter((a) => Date.parse(a.at) >= startedAt)
  const failure = current?.status === 'failed' ? [...current.steps].reverse().find((s) => s.status === 'failed') : undefined
  const h = health.data
  const layerState = layers.data
  const incidentLayers = new Set<'rules' | 'ml' | 'llm'>()
  for (const alert of detected) {
    if (alert.rule_id.startsWith('R6_')) incidentLayers.add('ml')
    else if (alert.rule_id.startsWith('R7_')) incidentLayers.add('llm')
    else if (/^R[1-5]_/.test(alert.rule_id)) incidentLayers.add('rules')
  }
  const alertingLayers = attack ? incidentLayers : new Set(layerState?.alerting ?? [])
  const layerCount = alertingLayers.size
  const agreement = attack
    ? layerCount === 3 ? 'full' : layerCount === 2 ? 'partial' : layerCount === 1 ? 'single' : 'none'
    : layerState?.agreement ?? 'loading'
  const consensusLabel = agreement === 'full' ? 'Confirmed by all 3 monitors'
    : agreement === 'partial' ? 'Confirmed by 2 monitors'
      : agreement === 'single' ? 'Detected by 1 monitor'
        : agreement === 'none' ? 'No threat detected' : 'Checking monitors…'
  const rulesAvailable = Boolean(h?.engine_running && h.rpc_ok)

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

      <div className="mt-6 overflow-hidden rounded-2xl border border-ink-700 bg-white" data-testid="surveillance-layers">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-700 px-5 py-4">
          <div>
            <Eyebrow>Security monitoring</Eyebrow>
            <p className="mt-1 text-[13px] text-fog-400">Three independent monitors watch every position and cross-check each other.</p>
          </div>
          <Pill tone={agreement === 'full' ? 'bad' : agreement === 'partial' ? 'warn' : 'neutral'}>{consensusLabel}</Pill>
        </div>
        <div className="relative grid px-5 py-2 md:grid-cols-3 md:divide-x md:divide-ink-700">
          <DetectionLayer index="01" name="Blockchain safety checks" id="Deterministic controls" detail="Verifies bridge backing, collateral movements, market liquidity, withdrawals and emergency freezes." available={rulesAvailable} alerting={alertingLayers.has('rules')} />
          <DetectionLayer index="02" name="Attack pattern detection" id="Machine learning" detail="Compares live market behavior with normal activity to catch unusual attack sequences." available={Boolean(layerState?.ml_available)} alerting={alertingLayers.has('ml')} />
          <DetectionLayer index="03" name="Independent risk review" id="AI analysis" detail="Reviews the same evidence independently and explains whether the events form a coordinated attack." available={Boolean(layerState?.agent_available)} alerting={alertingLayers.has('llm')} />
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
              <table className="mt-3 w-full table-fixed text-left text-[13px]" data-testid="detections">
                <colgroup><col /><col className="w-[100px]" /><col className="w-[96px]" /></colgroup>
                <thead className="font-mono text-[10px] uppercase tracking-[0.14em] text-fog-500">
                  <tr><th className="py-2 pr-3">Rule</th><th className="pr-3">Severity</th><th className="text-right">Block</th></tr>
                </thead>
                <tbody>
                  {detected.length === 0 && <tr><td colSpan={3} className="py-3 text-fog-400">Nothing abnormal yet.</td></tr>}
                  {detected.map((a) => (
                    <tr key={a.id} className="border-t border-ink-700 align-top">
                      <td className="py-3 pr-3"><div className="font-medium leading-5">{ruleLabel(a.rule_id)}</div><div className="text-[12px] text-fog-400">{a.explanation}</div></td>
                      <td className="py-3 pr-3"><Severity severity={a.severity} /></td>
                      <td className="py-3 text-right leading-5"><BlockLink explorer={explorer} block={a.block_number} /></td>
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
                      ['Incident', <span key="id" className="font-mono">{incident.id}</span>],
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
              <div className="flex items-center justify-between"><b>Discord</b>
                {config.data && <Pill tone={config.data.discord_configured ? 'ok' : 'warn'}>{config.data.discord_configured ? 'webhook set' : 'webhook missing'}</Pill>}
              </div>
              {config.data && !config.data.discord_configured && (
                <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
                  No Discord webhook yet: add ALERT_WEBHOOK_URL to .env and restart the backend. The summary below was prepared but not sent.
                </p>
              )}
              {!summary ? <p className="mt-3 text-fog-400">One summary alert goes out as soon as the fraud is detected.</p> : (
                <div className="mt-3 flex items-start gap-4 rounded-xl border border-ink-700 p-4" data-testid="discord-summary">
                  <ChannelLogo channel="discord" className="mt-0.5 h-7 w-7 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <b>Fraud alert{incident ? `: ${incident.title}` : ''}</b>
                      <Pill tone={summary.status === 'sent' ? 'ok' : summary.status === 'failed' ? 'bad' : 'warn'}>
                        {summary.status === 'sent' ? 'sent ✓' : summary.status === 'failed' ? `failed${summary.http_status ? ` ${summary.http_status}` : ''}` : 'not sent'}
                      </Pill>
                    </div>
                    <div className="mt-1 text-[13px] text-fog-400">
                      {formatUtc(summary.at)}{incident && ` · exposure ${formatUsd(incident.exposure_usd)}`}{summary.attachment && ` · ${summary.attachment} attached`}
                    </div>
                  </div>
                </div>
              )}
              {clicks.length > 0 && (
                <div className="mt-4" data-testid="discord-actions">
                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-fog-400">Actions taken from Discord</div>
                  <ul className="mt-2 space-y-2">
                    {clicks.map((a) => <DiscordActionRow key={a.id} action={a} explorer={explorer} />)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
