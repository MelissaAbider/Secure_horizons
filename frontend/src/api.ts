import type {
  Alert, Decision, DemoRun, DemoVariant, Dependency, EvalMetrics, Health, Incident,
  SeriesPoint, StateResponse, VerifyResult,
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

export const api = {
  health(): Promise<Health> { return isFixtureMode() ? fixtureDb.health() : getJson('/api/health') },
  state(): Promise<StateResponse> { return isFixtureMode() ? fixtureDb.state() : getJson('/api/state') },
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
  demoRun(runId: string): Promise<DemoRun> {
    return isFixtureMode() ? fixtureDb.demoRun(runId) : getJson(`/api/demo/runs/${encodeURIComponent(runId)}`)
  },
}
