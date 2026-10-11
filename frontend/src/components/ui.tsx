import type { ReactNode } from 'react'
import { formatBpsPct, severityClass, shortHash, toneClass, type Tone } from '../lib/format'

export function Panel({ title, right, children, className = '', testId }: {
  title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; testId?: string
}) {
  return (
    <section data-testid={testId} className={`rounded-3xl border border-ink-700 bg-white shadow-soft ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-700 px-5 py-3">
          <h2 className="font-mono text-[12px] font-medium uppercase tracking-[0.2em] text-fog-300">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function SeverityBadge({ severity, testId }: { severity: string; testId?: string }) {
  return (
    <span data-testid={testId} className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-[0.12em] text-white ${severityClass[severity] ?? 'bg-slate-600'}`}>
      {severity.toUpperCase()}
    </span>
  )
}

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'violet' }) {
  const cls = {
    neutral: 'border-ink-600 bg-ink-800 text-fog-300',
    ok: 'border-green-200 text-green-700 bg-green-50',
    warn: 'border-amber-200 text-amber-700 bg-amber-50',
    bad: 'border-red-200 text-red-600 bg-red-50',
    violet: 'border-blue-200 text-blue-700 bg-blue-50',
  }[tone]
  return <span className={`inline-flex items-center rounded border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.12em] ${cls}`}>{children}</span>
}

export function ToneBar({ bps, tone, label }: { bps: number; tone: Tone; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(bps / 100)))
  return (
    <div className="flex items-center gap-3">
      <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}
        data-tone={tone} className="h-2 w-28 overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full ${toneClass[tone]}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-fog-100">{formatBpsPct(bps)}</span>
    </div>
  )
}

export function Stat({ label, value, hint, accent, testId }: {
  label: string; value: ReactNode; hint?: string; accent?: 'bad' | 'ok' | 'neutral'; testId?: string
}) {
  const color = accent === 'bad' ? 'text-red-600' : accent === 'ok' ? 'text-signal-violet' : 'text-fog-100'
  return (
    <div data-testid={testId} className="rounded-3xl border border-ink-700 bg-white p-5 shadow-soft">
      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-fog-500">{label}</div>
      <div className={`mt-2 font-display text-4xl font-semibold tracking-tight tabular-nums ${color}`}>{value}</div>
      {hint && <div className="mt-2 text-sm text-fog-500">{hint}</div>}
    </div>
  )
}

export function TxLink({ hash, network }: { hash: string | null | undefined; network?: string }) {
  if (!hash) return <span className="text-fog-500">—</span>
  if (network === 'local' || hash.startsWith('0xdry')) {
    return <span className="font-mono text-fog-300" title={network === 'local' ? 'local chain: no explorer' : 'dry run: no transaction'}>{shortHash(hash)}</span>
  }
  return (
    <a href={`${__EXPLORER_URL__}/tx/${hash}`} target="_blank" rel="noreferrer"
      className="font-mono text-signal-violet underline decoration-dotted underline-offset-2 hover:text-fog-100">
      {shortHash(hash)}
    </a>
  )
}

export function Banner({ tone, children, testId }: { tone: 'yellow' | 'gray' | 'red' | 'amber'; children: ReactNode; testId?: string }) {
  const cls = {
    yellow: 'border-yellow-200 bg-yellow-50 text-yellow-800',
    gray: 'border-ink-600 bg-ink-800 text-fog-300',
    red: 'border-red-200 bg-red-50 text-red-600',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
  }[tone]
  return <div data-testid={testId} role="status" className={`rounded-md border px-4 py-2 font-mono text-[12px] uppercase tracking-[0.12em] ${cls}`}>{children}</div>
}

export function Waiting() {
  return (
    <div data-testid="waiting-first-block" className="flex items-center gap-4 rounded-xl border border-ink-700 bg-ink-850 p-8 text-fog-300">
      <span className="h-3 w-3 animate-ping rounded-full bg-signal-violet" />
      <div>
        <div className="text-lg font-semibold text-fog-100">Waiting for first block</div>
        <div className="text-sm">The engine has not read the chain yet.</div>
      </div>
    </div>
  )
}

export function ErrorText({ children }: { children: ReactNode }) {
  return <p role="alert" className="mt-2 text-sm font-medium text-red-600">{children}</p>
}
