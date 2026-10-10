// Mirror of backend/models.py (TASKS.md 2.6). Owner: T0. Change both files in the same commit.
// Token amounts are strings in base units, rates are integer basis points, times are ISO 8601 UTC strings.

export type Severity = 'info' | 'warning' | 'high' | 'critical';
export type Network = 'local' | 'fuji' | 'replay';
export type ActionType =
  | 'NOTIFY'
  | 'PAUSE_DEPOSITS'
  | 'EMERGENCY_WITHDRAW'
  | 'FULL_EXIT'
  | 'UNPAUSE_DEPOSITS'
  | 'OPEN_INCIDENT';
export type ActionMode = 'auto' | 'human';
export type ActionStatus =
  | 'planned'
  | 'executed'
  | 'failed'
  | 'skipped'
  | 'pending_approval'
  | 'approved'
  | 'rejected';
export type ParamValue = string | number | boolean | string[];

export interface ReserveSnapshot {
  deployment_id: string;
  asset: string;
  asset_address: string;
  decimals: number;
  total_supplied: string;
  total_borrowed: string;
  available_liquidity: string;
  total_collateral: string;
  utilization_bps: number;
  supply_apy_bps: number;
  borrow_apy_bps: number;
  ltv_bps: number;
  borrowable: boolean;
  frozen: boolean;
  paused: boolean;
  price_usd: number;
}

export interface TokenSnapshot {
  symbol: string;
  address: string;
  decimals: number;
  total_supply: string;
  backing: string | null;
  backing_ratio_bps: number | null;
  price_usd: number;
}

export interface PositionSnapshot {
  wallet: string;
  deployment_id: string;
  asset: string;
  supplied: string;
  withdrawable_now: string;
  withdrawable_ratio_bps: number;
  value_usd: number;
  withdrawable_usd: number;
}

export interface VaultStatus {
  address: string;
  deposits_paused: boolean;
  idle_balances: Record<string, string>;
}

export interface Snapshot {
  network: Network;
  chain_id: number;
  block_number: number;
  block_time: string;
  source: string;
  reserves: ReserveSnapshot[];
  tokens: TokenSnapshot[];
  positions: PositionSnapshot[];
  vault: VaultStatus;
}

export interface Alert {
  id: string;
  rule_id: string;
  severity: Severity;
  network: Network;
  deployment_id: string | null;
  asset: string | null;
  block_number: number;
  block_time: string;
  detected_at: string;
  title: string;
  explanation: string;
  metrics: Record<string, ParamValue>;
  exposure_usd: number;
  rules_version: string;
}

export interface Action {
  type: ActionType;
  mode: ActionMode;
  status: ActionStatus;
  params: Record<string, ParamValue>;
  tx_hash: string | null;
  amount: string | null;
  executed_at: string | null;
  note: string | null;
}

export interface Decision {
  id: string;
  created_at: string;
  network: Network;
  block_number: number;
  alert_ids: string[];
  severity: Severity;
  exposure_usd: number;
  withdrawable_usd: number;
  exit_cost_bps: number;
  matrix_cell: string;
  rationale: string;
  actions: Action[];
  inputs_hash: string;
  rules_version: string;
  playbook_version: string;
  record_hash: string | null;
  anchor_tx: string | null;
  anchor_block: number | null;
}

export interface VerifyResult {
  decision_id: string;
  match: boolean;
  stored_hash: string | null;
  recomputed_hash: string | null;
  anchored: boolean;
  anchor_tx: string | null;
  anchor_block: number | null;
  diffs: string[];
}

export interface DoraCriteria {
  critical_services_affected: boolean;
  clients_affected_pct: number;
  clients_affected_count: number;
  transactions_affected_value_pct: number;
  counterparts_affected_pct: number;
  transactions_affected_count_pct: number;
  relevant_clients_affected: boolean;
  duration_hours: number;
  critical_service_downtime_hours: number;
  member_states_affected: number;
  reputational_impact: boolean;
  data_losses: boolean;
  malicious_unauthorised_access: boolean;
  economic_impact_eur: number;
}

export interface DoraDeadlines {
  initial_notification_due: string;
  intermediate_report_due: string;
  final_report_due: string;
}

export interface DoraAssessment {
  criteria: DoraCriteria;
  thresholds_met: string[];
  is_major: boolean;
  legal_basis: string;
  aware_at: string;
  classified_at: string;
  deadlines: DoraDeadlines;
  report_markdown: string;
  ai_drafted_sections: string[];
  submitted: boolean;
  submitted_by: string | null;
  submitted_at: string | null;
}

export interface TimelineEvent {
  at: string;
  block_number: number | null;
  kind: 'alert' | 'decision' | 'action' | 'human' | 'chain' | 'dora';
  text: string;
  ref: string | null;
}

export interface Incident {
  id: string;
  title: string;
  status: 'open' | 'contained' | 'resolved';
  severity: Severity;
  opened_at: string;
  detected_at: string;
  contained_at: string | null;
  alert_ids: string[];
  decision_ids: string[];
  exposure_usd: number;
  saved_usd: number;
  at_risk_usd: number;
  dora: DoraAssessment | null;
  timeline: TimelineEvent[];
}

export interface Dependency {
  id: string;
  name: string;
  kind: string;
  provider: string;
  criticality: 'critical' | 'important' | 'standard';
  supports: string[];
  fallback: string | null;
  status: 'ok' | 'degraded' | 'down' | 'unknown';
}

export interface SeriesPoint {
  block_number: number;
  block_time: string;
  utilization_bps: number;
  available_liquidity: string;
  supply_apy_bps: number;
  withdrawable_ratio_bps: number | null;
  backing_ratio_bps: number | null;
}

export interface StateTotals {
  value_usd: number;
  withdrawable_usd: number;
  idle_usd: number;
  at_risk_usd: number;
}

export interface StateResponse {
  network: Network;
  chain_id: number;
  block_number: number;
  block_time: string;
  updated_at: string;
  risk_level: Severity;
  open_incident_id: string | null;
  vault: VaultStatus;
  positions: PositionSnapshot[];
  reserves: ReserveSnapshot[];
  tokens: TokenSnapshot[];
  totals: StateTotals;
}

export interface Health {
  status: 'ok' | 'degraded';
  network: Network;
  chain_id: number;
  block_number: number;
  rpc_ok: boolean;
  engine_running: boolean;
  version: string;
}

export interface DemoRun {
  run_id: string;
  kind: 'attack' | 'normal' | 'reset' | 'seed';
  variant: string | null;
  seed: number | null;
  status: 'running' | 'done' | 'failed';
  started_at: string;
  finished_at: string | null;
  params: Record<string, ParamValue>;
  log: string[];
}

export interface RunRecord {
  run_id: string;
  network: Network;
  label: 'attack' | 'normal';
  variant: string;
  seed: number;
  params: Record<string, ParamValue>;
  start_block: number;
  end_block: number;
  attack_start_block: number | null;
  phase_blocks: Record<string, number>;
  treasury_supplied_at_start: Record<string, string>;
}

export interface EvalMetrics {
  generated_at: string;
  rules_version: string;
  synthetic: Record<string, ParamValue>;
  mainnet_replay: Record<string, ParamValue> | null;
  notes: string[];
}
