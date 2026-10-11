import type { Alert, SeriesPoint } from '../types'
import { unitsToNumber } from './format'

export interface ChartPoint {
  block: number
  utilization: number
  liquidity: number
  withdrawable: number | null
  apy: number
  backing: number | null
}

export function toChartPoints(points: SeriesPoint[], decimals: number): ChartPoint[] {
  return points.map((p) => ({
    block: p.block_number,
    utilization: p.utilization_bps / 100,
    liquidity: unitsToNumber(p.available_liquidity, decimals),
    withdrawable: p.withdrawable_ratio_bps === null ? null : p.withdrawable_ratio_bps / 100,
    apy: p.supply_apy_bps / 100,
    backing: p.backing_ratio_bps === null ? null : p.backing_ratio_bps / 100,
  }))
}

/** Alerts to draw on a reserve's charts: global ones (deployment_id null) or same deployment, inside the series window. */
export function alertsForReserve(alerts: Alert[], dep: string, _asset: string, minBlock: number, maxBlock: number): Alert[] {
  return alerts
    .filter((a) => (a.deployment_id === null || a.deployment_id === dep) && a.block_number >= minBlock && a.block_number <= maxBlock)
    .sort((a, b) => a.block_number - b.block_number)
}
