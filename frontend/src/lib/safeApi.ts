// The connected Safe (T10 routes in backend/api/safe.py): status, owner signatures relayed by the platform, allocations.
import { API_URL, ApiError } from '../api'

export interface Integration { id: string; protocol: string; asset: string; label: string }
export interface SafeStatus {
  network: string
  chain_id: number
  explorer_url: string
  integrations_available: Integration[]
  connected: boolean
  owner?: string
  safe?: string
  module?: string
  operator?: string
  module_enabled?: boolean
  root?: string
  seal_status?: 'none' | 'sealed' | 'stale'
  sealed_integrations?: string[]
  seal_tx?: string | null
  balances?: Record<string, string>
  positions?: { integration: string; supplied: string }[]
  decimals?: Record<string, number>
}
export interface SafeRequest { safe_tx_hash: string; typed_data: unknown; summary: string; action: string; root?: string }
export interface Decision { verdict: 'EXECUTED' | 'REFUSED'; reason: string | null; detail?: string; txs: string[] }

async function call<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  const res = await fetch(`${API_URL}/api/safe${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); if (j && typeof j.detail === 'string') detail = j.detail } catch { /* not json */ }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const safeApi = {
  status: () => call<SafeStatus>(''),
  connect: (owner: string) => call<SafeStatus>('/connect', { owner }),
  prepare: (action: 'enable_module' | 'seal', integrations: string[] = []) => call<SafeRequest>('/prepare', { action, integrations }),
  submit: (safeTxHash: string, signature: string) => call<{ tx_hash: string; status: SafeStatus }>('/submit', { safe_tx_hash: safeTxHash, signature }),
  fund: () => call<{ txs: string[]; status: SafeStatus }>('/fund', {}),
  allocate: (integration: string, action: 'deposit' | 'withdraw', amount: string) => call<Decision>('/allocate', { integration, action, amount }),
}
