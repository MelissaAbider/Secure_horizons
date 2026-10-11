"""Shared data models (TASKS.md section 2.6). Owner: T0. FROZEN: change only through TASKS.md 2.12
(write the request in docs/contract-requests.md). Started from the T4 shim (CR-001) and completed by T0.

Conventions (TASKS.md 2.5):
- Token amounts: strings in base units ("150000000000000000000" = 150 WETH). Never a float on-chain amount.
- Dollar values: float, for display and exposure.
- Rates and ratios: integers in basis points (1 % = 100 bps).
- Time: UTC datetime with timezone, serialized ISO 8601. Always keep the block number too.
- Assets by symbol (USDC, WETH, rsETH). Deployments by id (lend-eth, lend-avax).
- JSON keys: snake_case. Every model key is always present, null when empty (never exclude_none).
- Ids: alert ALT-<network>-<block>-<rule_id>-<deployment_id or global>-<asset or all>;
  decision DEC-<network>-<block>-<n>; incident INC-<yyyymmdd>-<nnn>; run RUN-<yyyymmddHHMMSS>-<kind>-<seed>.

frontend/src/types.ts mirrors this file field by field: change both in the same commit.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "high", "critical"]
Network = Literal["local", "fuji", "replay"]
ActionType = Literal["NOTIFY", "PAUSE_DEPOSITS", "EMERGENCY_WITHDRAW", "FULL_EXIT", "UNPAUSE_DEPOSITS", "OPEN_INCIDENT"]
ActionMode = Literal["auto", "human"]
ActionStatus = Literal["planned", "executed", "failed", "skipped", "pending_approval", "approved", "rejected"]
ParamValue = Union[str, int, float, bool, list[str]]


# ---------- Snapshot (T3) ----------

class ReserveSnapshot(BaseModel):
    deployment_id: str
    asset: str
    asset_address: str
    decimals: int
    total_supplied: str
    total_borrowed: str
    available_liquidity: str
    total_collateral: str
    utilization_bps: int
    supply_apy_bps: int
    borrow_apy_bps: int
    ltv_bps: int
    borrowable: bool
    frozen: bool
    paused: bool
    price_usd: float


class TokenSnapshot(BaseModel):
    symbol: str
    address: str
    decimals: int
    total_supply: str
    backing: Optional[str] = None            # rsETH display compatibility only
    backing_ratio_bps: Optional[int] = None  # rsETH display compatibility only
    price_usd: float
    bridge_source_locked: Optional[str] = None
    bridge_destination_released: Optional[str] = None
    bridge_source_nonce: Optional[int] = None
    bridge_destination_nonce: Optional[int] = None
    bridge_paused: Optional[bool] = None


class PositionSnapshot(BaseModel):
    wallet: str
    deployment_id: str
    asset: str
    supplied: str
    withdrawable_now: str
    withdrawable_ratio_bps: int
    value_usd: float
    withdrawable_usd: float


class VaultStatus(BaseModel):
    address: str
    deposits_paused: bool
    idle_balances: dict[str, str] = Field(default_factory=dict)  # symbol -> base units


class Snapshot(BaseModel):
    network: Network
    chain_id: int
    block_number: int
    block_time: datetime
    source: str  # "live" for the collector, "replay" for T7
    reserves: list[ReserveSnapshot] = Field(default_factory=list)
    tokens: list[TokenSnapshot] = Field(default_factory=list)
    positions: list[PositionSnapshot] = Field(default_factory=list)
    vault: VaultStatus


# ---------- Alert (T3) ----------

class Alert(BaseModel):
    id: str
    rule_id: str
    severity: Severity
    network: Network
    deployment_id: Optional[str] = None  # None for global rules (R1)
    asset: Optional[str] = None
    block_number: int
    block_time: datetime
    detected_at: datetime
    title: str
    explanation: str
    metrics: dict[str, ParamValue] = Field(default_factory=dict)
    exposure_usd: float
    rules_version: str


# ---------- Response and evidence (T4) ----------

class Action(BaseModel):
    type: ActionType
    mode: ActionMode
    status: ActionStatus
    params: dict[str, ParamValue] = Field(default_factory=dict)
    tx_hash: Optional[str] = None
    amount: Optional[str] = None
    executed_at: Optional[datetime] = None
    note: Optional[str] = None


class Decision(BaseModel):
    id: str
    created_at: datetime
    network: Network
    block_number: int
    alert_ids: list[str] = Field(default_factory=list)
    severity: Severity
    exposure_usd: float
    withdrawable_usd: float
    exit_cost_bps: int = 0
    matrix_cell: str
    rationale: str
    actions: list[Action] = Field(default_factory=list)
    inputs_hash: str
    rules_version: str
    playbook_version: str
    record_hash: Optional[str] = None
    anchor_tx: Optional[str] = None
    anchor_block: Optional[int] = None


class VerifyResult(BaseModel):
    decision_id: str
    match: bool
    stored_hash: Optional[str] = None
    recomputed_hash: Optional[str] = None
    anchored: bool
    anchor_tx: Optional[str] = None
    anchor_block: Optional[int] = None
    diffs: list[str] = Field(default_factory=list)


# ---------- Incident and DORA (T5) ----------

class DoraCriteria(BaseModel):
    critical_services_affected: bool
    clients_affected_pct: float
    clients_affected_count: int
    transactions_affected_value_pct: float
    counterparts_affected_pct: float = 0
    transactions_affected_count_pct: float = 0
    relevant_clients_affected: bool = False
    duration_hours: float
    critical_service_downtime_hours: float
    member_states_affected: int
    reputational_impact: bool
    data_losses: bool
    malicious_unauthorised_access: bool
    economic_impact_eur: float


class DoraDeadlines(BaseModel):
    initial_notification_due: datetime
    intermediate_report_due: datetime
    final_report_due: datetime


class DoraAssessment(BaseModel):
    criteria: DoraCriteria
    thresholds_met: list[str] = Field(default_factory=list)
    is_major: bool
    legal_basis: str
    aware_at: datetime
    classified_at: datetime
    deadlines: DoraDeadlines
    report_markdown: str
    ai_drafted_sections: list[str] = Field(default_factory=list)
    submitted: bool = False
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None


class TimelineEvent(BaseModel):
    at: datetime
    block_number: Optional[int] = None
    kind: Literal["alert", "decision", "action", "human", "chain", "dora"]
    text: str
    ref: Optional[str] = None


class Incident(BaseModel):
    id: str
    title: str
    status: Literal["open", "contained", "resolved"]
    severity: Severity
    opened_at: datetime
    detected_at: datetime
    contained_at: Optional[datetime] = None
    alert_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    exposure_usd: float
    saved_usd: float
    at_risk_usd: float
    dora: Optional[DoraAssessment] = None
    timeline: list[TimelineEvent] = Field(default_factory=list)


class Dependency(BaseModel):
    id: str
    name: str
    kind: str
    provider: str
    criticality: Literal["critical", "important", "standard"]
    supports: list[str] = Field(default_factory=list)
    fallback: Optional[str] = None
    status: Literal["ok", "degraded", "down", "unknown"]


# ---------- State API (T3) ----------

class SeriesPoint(BaseModel):
    block_number: int
    block_time: datetime
    utilization_bps: int
    available_liquidity: str
    supply_apy_bps: int
    withdrawable_ratio_bps: Optional[int] = None
    backing_ratio_bps: Optional[int] = None


class StateResponse(BaseModel):
    network: Network
    chain_id: int
    block_number: int
    block_time: datetime
    updated_at: datetime
    risk_level: Severity
    open_incident_id: Optional[str] = None
    vault: VaultStatus
    positions: list[PositionSnapshot] = Field(default_factory=list)
    reserves: list[ReserveSnapshot] = Field(default_factory=list)
    tokens: list[TokenSnapshot] = Field(default_factory=list)
    totals: dict[str, float] = Field(default_factory=dict)  # value_usd, withdrawable_usd, idle_usd, at_risk_usd


# ---------- API health (T3), demo runs (T2), evaluation (T7) ----------

class Health(BaseModel):
    status: Literal["ok", "degraded"]
    network: Network
    chain_id: int
    block_number: int
    rpc_ok: bool
    engine_running: bool
    version: str


class DemoStep(BaseModel):
    """One JSON line of a scenario run (TASKS.md T2 Outputs), kept structured for the dashboard."""

    step: str
    status: Literal["ok", "info", "blocked", "failed"]
    block: Optional[int] = None
    tx_hash: Optional[str] = None
    msg: str
    at: datetime


class DemoRun(BaseModel):
    run_id: str  # RUN-<yyyymmddHHMMSS>-<kind>-<seed>
    kind: Literal["attack", "normal", "reset", "seed"]
    variant: Optional[str] = None  # default | slow | usdc
    seed: Optional[int] = None
    status: Literal["running", "done", "failed"]
    started_at: datetime
    finished_at: Optional[datetime] = None
    params: dict[str, ParamValue] = Field(default_factory=dict)
    log: list[str] = Field(default_factory=list)
    steps: list[DemoStep] = Field(default_factory=list)  # the same run, structured (tx hashes for explorer links)


class RunRecord(BaseModel):
    """Ground truth written by every scenario run (T2) to data/runs/<run_id>.json, read by T7."""

    run_id: str
    network: Network
    label: Literal["attack", "normal"]
    variant: str
    seed: int
    params: dict[str, ParamValue] = Field(default_factory=dict)
    start_block: int
    end_block: int
    attack_start_block: Optional[int] = None  # block of the forgedRelease tx
    phase_blocks: dict[str, int] = Field(default_factory=dict)  # forged_mint, collateral_deposit, first_borrow, liquidity_zero, protocol_freeze
    treasury_supplied_at_start: dict[str, str] = Field(default_factory=dict)  # "<deployment_id>:<asset>" -> base units


class EvalMetrics(BaseModel):
    """Written by T7 to data/eval/metrics.json, served by GET /api/metrics."""

    generated_at: datetime
    rules_version: str
    # runs_attack, runs_normal, detection_rate (0..1), false_positive_rate (0..1),
    # ttd_blocks_p50, ttd_blocks_p90 (-1 when nothing is detected), saved_pct_mean (0..100), baseline_saved_pct_mean (0..100)
    synthetic: dict[str, ParamValue] = Field(default_factory=dict)
    mainnet_replay: Optional[dict[str, ParamValue]] = None  # phase 2
    notes: list[str] = Field(default_factory=list)


class NotificationDelivery(BaseModel):
    """One alert notification attempt (backend/alerting.py), served by GET /api/notifications."""

    at: datetime
    channel: Literal["discord"]
    status: Literal["sent", "failed", "not_configured"]
    rule_ids: list[str] = Field(default_factory=list)
    incident_id: Optional[str] = None
    attachment: Optional[str] = None  # file name of the attached DORA draft, if any
    http_status: Optional[int] = None
