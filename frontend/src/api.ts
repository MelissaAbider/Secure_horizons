import type {
  AgentCycle, AgentMoveRecord, AgentStatus, Alert, Decision, DemoRun, DemoVariant, Dependency, DiscordAction, EvalMetrics,
  Health, Incident, MonitoringLayers, NotificationDelivery, SeriesPoint, StateResponse, VerifyResult,
} from './types'
import { ApiError } from './apiError'
import { fixtureDb } from './fixtureDb'

export { ApiError }
export type { DemoVariant }

// production: '' → relative /api/... calls, same origin (nginx from T8 serves dist/ and /api)
export const API_URL: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

export function isFixtureMode(): boolean { return import.meta.env.VITE_USE_FIXTURES === 'true' }
export function isNoSnapshotYet(e: unknown): boolean { return e instanceof ApiError && e.status === 503 }

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); if (j && typeof j.detail === 'string') detail = j.detail } catch { /* not json */ }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`)
  }
  return res
}
async function getJson<T>(path: string): Promise<T> { return (await request(path)).json() as Promise<T> }
async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = body === undefined
    ? { method: 'POST' }
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  return (await request(path, init)).json() as Promise<T>
}

export interface NotificationsConfig { discord_configured: boolean; network: string; explorer_url: string }

export const api = {
  health(): Promise<Health> { return isFixtureMode() ? fixtureDb.health() : getJson('/api/health') },
  state(): Promise<StateResponse> { return isFixtureMode() ? fixtureDb.state() : getJson('/api/state') },
  async monitoringLayers(): Promise<MonitoringLayers> {
    if (isFixtureMode()) return { alerting: [], agreement: 'none', agent_available: true, ml_available: true }
    const res = await request('/api/state')
    const raw = res.headers.get('X-Monitoring-Layers')
    if (!raw) throw new ApiError(502, 'Monitoring layer status header missing')
    return JSON.parse(raw) as MonitoringLayers
  },
  series(deploymentId: string, asset: string, limit = 300): Promise<SeriesPoint[]> {
    if (isFixtureMode()) return fixtureDb.series(deploymentId, asset, limit)
    const q = new URLSearchParams({ deployment_id: deploymentId, asset, limit: String(limit) })
    return getJson(`/api/series?${q.toString()}`)
  },
  alerts(sinceBlock = 0): Promise<Alert[]> {
    return isFixtureMode() ? fixtureDb.alerts(sinceBlock) : getJson(`/api/alerts?since_block=${sinceBlock}`)
  },
  decisions(): Promise<Decision[]> { return isFixtureMode() ? fixtureDb.decisions() : getJson('/api/decisions') },
  approve(decisionId: string, body: { action_index: number; approver: string; approve: boolean }): Promise<Decision> {
    return isFixtureMode() ? fixtureDb.approve(decisionId, body)
      : postJson(`/api/decisions/${encodeURIComponent(decisionId)}/approve`, body)
  },
  verify(decisionId: string): Promise<VerifyResult> {
    return isFixtureMode() ? fixtureDb.verify(decisionId) : postJson(`/api/verify/${encodeURIComponent(decisionId)}`)
  },
  incidents(): Promise<Incident[]> { return isFixtureMode() ? fixtureDb.incidents() : getJson('/api/incidents') },
  incident(id: string): Promise<Incident> {
    return isFixtureMode() ? fixtureDb.incident(id) : getJson(`/api/incidents/${encodeURIComponent(id)}`)
  },
  async incidentReport(id: string): Promise<string> {
    if (isFixtureMode()) return fixtureDb.incidentReport(id)
    return (await request(`/api/incidents/${encodeURIComponent(id)}/report.md`)).text()
  },
  submitIncident(id: string, submittedBy: string): Promise<Incident> {
    return isFixtureMode() ? fixtureDb.submitIncident(id, submittedBy)
      : postJson(`/api/incidents/${encodeURIComponent(id)}/submit`, { submitted_by: submittedBy })
  },
  dependencies(): Promise<Dependency[]> { return isFixtureMode() ? fixtureDb.dependencies() : getJson('/api/dependencies') },
  metrics(): Promise<EvalMetrics> { return isFixtureMode() ? fixtureDb.metrics() : getJson('/api/metrics') },
  demoAttack(seed: number, variant: DemoVariant = 'default'): Promise<DemoRun> {
    return isFixtureMode() ? fixtureDb.demoAttack(seed, variant) : postJson('/api/demo/attack', { seed, variant })
  },
  demoReset(): Promise<DemoRun> { return isFixtureMode() ? fixtureDb.demoReset() : postJson('/api/demo/reset') },
  /** Discord attempts made by the alerting module, newest first (none in fixture mode). */
  notifications(): Promise<NotificationDelivery[]> { return isFixtureMode() ? Promise.resolve([]) : getJson('/api/notifications') },
  notificationsConfig(): Promise<NotificationsConfig> {
    return isFixtureMode()
      ? Promise.resolve({ discord_configured: false, network: 'fuji', explorer_url: 'https://testnet.snowtrace.io' })
      : getJson('/api/notifications/config')
  },
  /** Clicks on the withdraw buttons of the Discord alert, newest first (none in fixture mode). */
  discordActions(): Promise<DiscordAction[]> { return isFixtureMode() ? Promise.resolve([]) : getJson('/api/discord/actions') },
  /** The MCP tools the agent can call (names, descriptions, schemas). */
  agentTools(): Promise<{ name: string; description: string; read_only: boolean }[]> { return getJson('/api/agent/tools') },
  agentStatus(): Promise<AgentStatus> { return getJson('/api/agent/status') },
  agentCycles(): Promise<AgentCycle[]> { return isFixtureMode() ? Promise.resolve([]) : getJson('/api/agent/cycles') },
  agentMoves(): Promise<AgentMoveRecord[]> { return isFixtureMode() ? Promise.resolve([]) : getJson('/api/agent/moves') },
  agentRun(instructions: string): Promise<AgentCycle> { return postJson('/api/agent/run', { instructions }) },
  agentLoop(enabled: boolean, intervalS: number, instructions: string): Promise<AgentStatus> {
    return postJson('/api/agent/loop', { enabled, interval_s: intervalS, instructions })
  },
  agentApprove(moveId: string, approver: string): Promise<AgentMoveRecord> {
    return postJson(`/api/agent/moves/${encodeURIComponent(moveId)}/approve`, { approver })
  },
  incidentPdfUrl(id: string): string { return `${API_URL}/api/incidents/${encodeURIComponent(id)}/report.pdf` },
  demoRun(runId: string): Promise<DemoRun> {
    return isFixtureMode() ? fixtureDb.demoRun(runId) : getJson(`/api/demo/runs/${encodeURIComponent(runId)}`)
  },
}
