export const APP_NAME = 'Treasury Guard'
export const APP_VERSION = 'v8'

export const RULE_LABELS: Record<string, string> = {
  R1_BACKING_DROP: 'Bridged token backing drop',
  R2_LIQUIDITY_DROP: 'Market liquidity drop',
  R3_UTILIZATION_HIGH: 'Market utilization high',
  R4_POSITION_STUCK: 'Our position is stuck',
  R5_RESERVE_FROZEN: 'Reserve frozen or paused',
}
export function ruleLabel(id: string): string { return RULE_LABELS[id] ?? id }
export function ruleShort(id: string): string { return id.split('_')[0] }

export const ACTION_LABELS: Record<string, string> = {
  NOTIFY: 'Notify the team',
  PAUSE_DEPOSITS: 'Pause new deposits',
  EMERGENCY_WITHDRAW: 'Emergency withdrawal to the vault',
  FULL_EXIT: 'Full exit',
  UNPAUSE_DEPOSITS: 'Resume deposits',
  OPEN_INCIDENT: 'Open incident',
}
export function actionLabel(t: string): string { return ACTION_LABELS[t] ?? t }

export const DEPLOYMENT_LABELS: Record<string, string> = {
  'lend-eth': 'Lending protocol (Ethereum deployment)',
  'lend-avax': 'Lending protocol (Avalanche deployment)',
}
export function deploymentLabel(id: string | null): string {
  if (!id) return 'All deployments'
  return DEPLOYMENT_LABELS[id] ?? id
}
