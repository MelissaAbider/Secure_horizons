// In-memory backend used when VITE_USE_FIXTURES=true. Loads fixtures/*.json lazily
// (dynamic imports, so they are not bundled into the real build) and simulates writes.
import type {
  Alert, Decision, DemoRun, DemoVariant, Dependency, EvalMetrics, Health, Incident,
  SeriesPoint, StateResponse, VerifyResult,
} from './types'
import { ApiError } from './apiError'

const cache = new Map<string, unknown>()
async function load<T>(name: string, loader: () => Promise<{ default: unknown }>): Promise<T> {
  if (!cache.has(name)) cache.set(name, structuredClone((await loader()).default))
  return cache.get(name) as T
}
export function resetFixtureDb(): void { cache.clear() }

const L = {
  health: () => load<Health>('health', () => import('@fixtures/health.json')),
  state: () => load<StateResponse>('state', () => import('@fixtures/state.json')),
  series: () => load<Record<string, SeriesPoint[]> | SeriesPoint[]>('series', () => import('@fixtures/series.json')),
  alerts: () => load<Alert[]>('alerts', () => import('@fixtures/alerts.json')),
  decisions: () => load<Decision[]>('decisions', () => import('@fixtures/decisions.json')),
  verify: () => load<VerifyResult>('verify', () => import('@fixtures/verify.json')),
  incident: () => load<Incident>('incident', () => import('@fixtures/incident.json')),
  deps: () => load<Dependency[]>('deps', () => import('@fixtures/dependencies.json')),
  metrics: () => load<EvalMetrics>('metrics', () => import('@fixtures/metrics.json')),
  demo: () => load<DemoRun>('demo', () => import('@fixtures/demo_run.json')),
}

function runId(kind: string, seed: number): string {
  const d = new Date().toISOString().replace(/\D/g, '').slice(0, 14)
  return `RUN-${d}-${kind}-${seed}`
}
const runs = new Map<string, DemoRun>()

export const fixtureDb = {
  health: () => L.health(),
  state: () => L.state(),
  async series(dep: string, asset: string, limit: number): Promise<SeriesPoint[]> {
    const data = await L.series()
    const arr = Array.isArray(data) ? data : data[`${dep}:${asset}`] ?? []
    return arr.slice(-limit)
  },
  alerts: async (sinceBlock: number) => (await L.alerts()).filter((a) => a.block_number >= sinceBlock),
  decisions: () => L.decisions(),
  async approve(id: string, body: { action_index: number; approver: string; approve: boolean }): Promise<Decision> {
    const d = (await L.decisions()).find((x) => x.id === id)
    if (!d) throw new ApiError(404, 'decision not found')
    const a = d.actions[body.action_index]
    if (!a) throw new ApiError(400, 'action_index out of range')
    if (a.status !== 'pending_approval') throw new ApiError(409, `action is not pending approval (status=${a.status})`)
    a.status = body.approve ? 'executed' : 'rejected'
    a.note = (body.approve ? 'approved by ' : 'rejected by ') + body.approver
    a.executed_at = new Date().toISOString()
    return structuredClone(d)
  },
  async verify(id: string): Promise<VerifyResult> { return { ...(await L.verify()), decision_id: id } },
  async incidents(): Promise<Incident[]> { return [await L.incident()] },
  async incident(id: string): Promise<Incident> {
    const i = await L.incident()
    if (i.id !== id) throw new ApiError(404, 'incident not found')
    return i
  },
  async incidentReport(id: string): Promise<string> { return (await this.incident(id)).dora?.report_markdown ?? '' },
  async submitIncident(id: string, by: string): Promise<Incident> {
    const i = await this.incident(id)
    if (!i.dora) throw new ApiError(409, 'incident has no DORA assessment')
    if (i.dora.submitted) throw new ApiError(409, 'already submitted')
    i.dora.submitted = true
    i.dora.submitted_by = by
    i.dora.submitted_at = new Date().toISOString()
    return structuredClone(i)
  },
  dependencies: () => L.deps(),
  metrics: () => L.metrics(),
  async demoAttack(seed: number, variant: DemoVariant): Promise<DemoRun> {
    const r: DemoRun = { ...(await L.demo()), seed, variant, kind: 'attack', run_id: runId('attack', seed), status: 'running' }
    runs.set(r.run_id, r)
    setTimeout(() => { r.status = 'done'; r.finished_at = new Date().toISOString() }, 3000)
    return { ...r }
  },
  async demoReset(): Promise<DemoRun> {
    const r: DemoRun = { ...(await L.demo()), kind: 'reset', run_id: runId('reset', 0), status: 'done', log: ['Fixture mode: nothing happens on chain'] }
    runs.set(r.run_id, r)
    return { ...r }
  },
  async demoRun(id: string): Promise<DemoRun> {
    const r = runs.get(id)
    if (!r) throw new ApiError(404, 'run not found')
    return { ...r }
  },
}
