import { createContext, useContext, type ReactNode } from 'react'
import { api } from './api'
import { usePolling, type Polled } from './hooks/usePolling'
import type { Alert, Decision, Health, StateResponse } from './types'

interface DashboardData {
  health: Polled<Health>
  state: Polled<StateResponse>
  alerts: Polled<Alert[]>
  decisions: Polled<Decision[]>
}

const Ctx = createContext<DashboardData | null>(null)

/** Polls health, state, alerts and decisions once and shares them with every page. */
export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const health = usePolling(() => api.health(), 2000)
  const state = usePolling(() => api.state(), 2000)
  const alerts = usePolling(() => api.alerts(0), 2000)
  const decisions = usePolling(() => api.decisions(), 2000)
  return <Ctx.Provider value={{ health, state, alerts, decisions }}>{children}</Ctx.Provider>
}

export function useDashboardData(): DashboardData {
  const v = useContext(Ctx)
  if (!v) throw new Error('useDashboardData must be used inside DashboardDataProvider')
  return v
}

const OPERATOR_KEY = 'sh.operator'
export function getOperator(): string {
  try { return localStorage.getItem(OPERATOR_KEY) || 'dashboard-operator' } catch { return 'dashboard-operator' }
}
export function setOperator(v: string): void {
  try { localStorage.setItem(OPERATOR_KEY, v) } catch { /* storage unavailable */ }
}
