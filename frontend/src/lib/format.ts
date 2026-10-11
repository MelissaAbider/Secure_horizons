// Pure formatting helpers. Amounts in base units are always handled with BigInt.

export type Tone = 'ok' | 'warn' | 'bad'

const usdFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
export function formatUsd(n: number): string {
  return usdFmt.format(Number.isFinite(n) ? n : 0)
}

export function formatUnits(base: string, decimals: number, maxFrac = 2): string {
  let v: bigint
  try { v = BigInt(base) } catch { return '—' }
  const neg = v < 0n
  if (neg) v = -v
  const scale = 10n ** BigInt(decimals)
  let whole = v / scale
  const rem = v % scale
  let frac = ''
  if (maxFrac > 0 && decimals > 0) {
    const fracScale = 10n ** BigInt(maxFrac)
    // round half up on the requested digits
    let f = (rem * fracScale * 10n) / scale
    f = (f + 5n) / 10n
    if (f >= fracScale) { whole += 1n; f -= fracScale }
    frac = f.toString().padStart(maxFrac, '0').replace(/0+$/, '')
  }
  const wholeStr = whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return (neg ? '-' : '') + wholeStr + (frac ? '.' + frac : '')
}

// For charts only: precision 2 decimals.
export function unitsToNumber(base: string, decimals: number): number {
  try {
    const v = BigInt(base)
    const scale = 10n ** BigInt(decimals)
    return Number(v / scale) + Number(((v % scale) * 100n) / scale) / 100
  } catch { return 0 }
}

export function formatBpsPct(bps: number): string {
  return (Math.round(bps / 10) / 10).toFixed(1) + '%'
}

export function withdrawableTone(bps: number): Tone { return bps >= 8000 ? 'ok' : bps >= 5000 ? 'warn' : 'bad' }
export function utilizationTone(bps: number): Tone { return bps < 9000 ? 'ok' : bps < 9800 ? 'warn' : 'bad' }
export function backingTone(bps: number): Tone { return bps >= 9900 ? 'ok' : 'bad' }

export function shortHash(h: string): string {
  if (!h || h.length < 12) return h
  return `${h.slice(0, 6)}…${h.slice(-4)}`
}

export function formatCountdown(dueIso: string, nowMs: number): string {
  const diff = Date.parse(dueIso) - nowMs
  const abs = Math.abs(diff)
  const mins = Math.floor(abs / 60000)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  const d = Math.floor(h / 24)
  const body = h >= 48 ? `${d} d ${h % 24} h` : `${h} h ${String(m).padStart(2, '0')} min`
  return diff >= 0 ? `${body} left` : `overdue by ${body}`
}

export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
}

export function formatRate(r: number): string { return (r * 100).toFixed(1) + '%' }
export function formatPct(p: number): string { return p.toFixed(1) + '%' }
export function formatTtd(blocks: number): string {
  if (blocks < 0) return 'not detected'
  return `${blocks} block${blocks === 1 ? '' : 's'}`
}

export const toneClass: Record<Tone, string> = { ok: 'bg-green-600', warn: 'bg-amber-500', bad: 'bg-red-600' }
export const toneText: Record<Tone, string> = { ok: 'text-green-700', warn: 'text-amber-600', bad: 'text-rose-glow' }
export const severityClass: Record<string, string> = {
  info: 'bg-slate-500', warning: 'bg-amber-500', high: 'bg-orange-600', critical: 'bg-red-600',
}
export const SEVERITY_RANK: Record<string, number> = { info: 0, warning: 1, high: 2, critical: 3 }
