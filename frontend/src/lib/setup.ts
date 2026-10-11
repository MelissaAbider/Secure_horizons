// Onboarding for the asset manager: connect the Safe, pick protocols, set the agent, start monitoring.
// Follows "Le projet en bref" (p.1 and p.3). The MVP backend has no setup API (allowlist and mandates are
// phase 2), so the setup lives in this browser and can be downloaded as a policy file.

export type Network = 'fuji' | 'local'

export interface Protocol { id: string; label: string; available: boolean }
export const PROTOCOLS: Protocol[] = [
  { id: 'aave-usdc', label: 'Aave · USDC', available: true },
  { id: 'benqi-usdc', label: 'Benqi · USDC', available: true },
  { id: 'aave-weth', label: 'Aave · WETH', available: true },
  { id: 'other', label: 'Other…', available: false },
]

export interface Rules {
  maxPerProtocolPct: number
  maxLossPct: number
  humanAboveUsd: number
  circuitBreaker: boolean
  protocolCaps: Record<string, number> // extra caps turned from instructions, e.g. { 'aave-usdc': 30 }
}

export interface SetupState {
  safe: string
  network: Network
  threshold: number
  signers: number
  connected: boolean
  owner: string // the wallet that owns the Safe
  sealed: boolean // the owner signed a Merkle root for the ticked integrations
  protocols: string[] // integration ids, e.g. 'lend-eth:WETH'
  rules: Rules
  instructions: string
  agentSaved: boolean
  channels: { discord: boolean; telegram: boolean; slack: boolean; email: boolean }
  live: boolean
  liveSince: string | null
}

export const DEFAULT_INSTRUCTIONS = 'Capital preservation first.\nAim for 5 to 7% a year on stablecoins.\nPrefer protocols older than two years.\nAt most three moves a day.\nNever more than 30% on Aave.'

export function defaultSetup(): SetupState {
  return {
    safe: '', network: 'fuji', threshold: 1, signers: 1, connected: false, owner: '', sealed: false,
    protocols: ['lend-eth:WETH', 'lend-avax:USDC'],
    rules: { maxPerProtocolPct: 40, maxLossPct: 0.5, humanAboveUsd: 100000, circuitBreaker: true, protocolCaps: {} },
    instructions: DEFAULT_INSTRUCTIONS, agentSaved: false,
    channels: { discord: true, telegram: false, slack: false, email: true },
    live: false, liveSince: null,
  }
}

const KEY = 'sh.setup'
export function loadSetup(): SetupState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return defaultSetup()
    const d = defaultSetup(), v = JSON.parse(raw) as Partial<SetupState>
    return { ...d, ...v, rules: { ...d.rules, ...(v.rules ?? {}) }, channels: { ...d.channels, ...(v.channels ?? {}) } }
  } catch { return defaultSetup() }
}
export function saveSetup(s: SetupState): void {
  try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* storage unavailable */ }
}

export function isAddress(a: string): boolean { return /^0x[0-9a-fA-F]{40}$/.test(a.trim()) }
export function shortAddr(a: string): string { return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a }

/** Steps done, in order. */
export function stepsDone(s: SetupState): boolean[] {
  return [s.connected, s.connected && s.sealed, s.agentSaved, s.live]
}

export interface RuleHint { line: string; protocolId: string; pct: number }
/**
 * Spots instructions that look like rules ("Never more than 30% on Aave").
 * While it stays an instruction the agent may ignore it; only signed rules are guaranteed.
 */
export function ruleHints(text: string, protocols: string[]): RuleHint[] {
  const out: RuleHint[] = []
  for (const line of text.split('\n')) {
    const m = line.match(/(?:never more than|no more than|at most|max(?:imum)?|jamais plus de|au plus)\s*(\d{1,3})\s*%\s*(?:on|in|sur|dans)\s+(aave|benqi)/i)
    if (!m) continue
    const name = m[2].toLowerCase()
    const pid = protocols.find((p) => p.startsWith(name)) ?? `${name}-usdc`
    out.push({ line: line.trim(), protocolId: pid, pct: Math.min(100, Number(m[1])) })
  }
  return out
}
