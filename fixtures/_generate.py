"""Regenerates every fixture from backend/models.py (TASKS.md 2.13). Owner: T0.

Run from the repo root: python -m fixtures._generate
All numbers are synthetic and follow TASKS.md 2.2 (initial state), 2.7 (rules R1..R5) and 2.8 (response matrix).
- snapshots_attack.jsonl: the scenario WITHOUT our reaction, one snapshot every 2 blocks (T3/T4 tests).
- snapshots_normal.jsonl: a normal day, no attack (zero alert expected).
- every other file: API responses WITH our reaction (R1 at block 45201812, everything pulled back to the vault).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from eth_utils import keccak

from backend.models import (
    Action,
    Alert,
    Decision,
    DemoRun,
    Dependency,
    DoraAssessment,
    DoraCriteria,
    DoraDeadlines,
    EvalMetrics,
    Health,
    Incident,
    PositionSnapshot,
    ReserveSnapshot,
    RunRecord,
    SeriesPoint,
    Snapshot,
    StateResponse,
    TimelineEvent,
    TokenSnapshot,
    VaultStatus,
    VerifyResult,
)

OUT = Path(__file__).resolve().parent
NET, CHAIN = "fuji", 43113
B0, FORGED, REACT, FREEZE, LAST = 45_201_800, 45_201_812, 45_201_813, 45_201_878, 45_201_880
T0 = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)
DEC = {"USDC": 6, "WETH": 18, "rsETH": 18}
PRICE = {"USDC": 1.0, "WETH": 2500.0, "rsETH": 2500.0}
ADDR = {  # the addresses anvil gives a fresh deployment in T1's order (TASKS.md T1)
    "USDC": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    "WETH": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    "rsETH": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
    "MockBridge": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
    "MockOracle": "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9",
    "lend-eth": "0x5FC8d32690cc91D4c39d9d3abcBD16989F875707",
    "lend-avax": "0x0165878A594ca255338adfa4d48449f69242Eb8F",
    "TreasuryVault": "0xa513E6E4b8f2a923D98304ec87F64353C4D5C853",
    "EvidenceRegistry": "0x2279B7A0a67DB372996a5FaB50D91eAA73d2eBe6",
}
VAULT = ADDR["TreasuryVault"]
RULES_PATH = Path(__file__).resolve().parents[1] / "backend" / "config" / "rules.yaml"
RULES_V = "sha256:" + hashlib.sha256(RULES_PATH.read_bytes()).hexdigest()
PLAYBOOK_V = "sha256:" + "0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5061728394a5b6c7d8e9f"  # placeholder
BOT_USDC_COLLATERAL = {"lend-eth": 4_500_000.0, "lend-avax": 3_000_000.0}  # TASKS.md 2.2
POSITIONS = [("lend-eth", "USDC", 400_000.0), ("lend-eth", "WETH", 150.0), ("lend-avax", "USDC", 300_000.0), ("lend-avax", "WETH", 100.0)]


def t(block: int) -> datetime:
    return T0 + timedelta(seconds=2 * (block - B0))


def units(amount: float, sym: str) -> str:
    return str(int(Decimal(str(amount)) * (Decimal(10) ** DEC[sym])))


def rates(util: float) -> tuple[int, int]:
    """Kinked model of TASKS.md 2.2: returns (supply_bps, borrow_bps)."""
    borrow = 100 + 300 * util / 0.8 if util <= 0.8 else 400 + 7500 * (util - 0.8) / 0.2
    return int(borrow * util * 0.85), int(borrow)


def reserve(dep: str, sym: str, supplied: float, borrowed: float, *, collateral: float, ltv: int,
            borrowable: bool = True, frozen: bool = False) -> ReserveSnapshot:
    util = borrowed / supplied if supplied else 0.0
    s_apy, b_apy = rates(util) if borrowable else (0, 0)
    return ReserveSnapshot(
        deployment_id=dep, asset=sym, asset_address=ADDR[sym], decimals=DEC[sym],
        total_supplied=units(supplied, sym), total_borrowed=units(borrowed, sym),
        available_liquidity=units(max(supplied - borrowed, 0.0), sym), total_collateral=units(collateral, sym),
        utilization_bps=int(round(util * 10_000)), supply_apy_bps=s_apy, borrow_apy_bps=b_apy, ltv_bps=ltv,
        borrowable=borrowable, frozen=frozen, paused=False, price_usd=PRICE[sym],
    )


def position(dep: str, sym: str, supplied: float, available: float) -> PositionSnapshot:
    withdrawable = min(supplied, max(available, 0.0))
    return PositionSnapshot(
        wallet=VAULT, deployment_id=dep, asset=sym, supplied=units(supplied, sym),
        withdrawable_now=units(withdrawable, sym),
        withdrawable_ratio_bps=int(round(withdrawable / supplied * 10_000)) if supplied else 0,
        value_usd=round(supplied * PRICE[sym], 2), withdrawable_usd=round(withdrawable * PRICE[sym], 2),
    )


def world(block: int, *, respond: bool, normal: bool = False) -> Snapshot:
    """Chain state at a block. respond=True applies our reaction: everything pulled back to the vault at REACT."""
    sup = {("lend-eth", "WETH"): 2000.0, ("lend-eth", "USDC"): 3_000_000.0, ("lend-avax", "WETH"): 1000.0, ("lend-avax", "USDC"): 2_000_000.0}
    bor = {("lend-eth", "WETH"): 1200.0, ("lend-eth", "USDC"): 1_800_000.0, ("lend-avax", "WETH"): 550.0, ("lend-avax", "USDC"): 1_100_000.0}
    treasury = {(d, a): v for d, a, v in POSITIONS}
    rs_supply = rs_backing = 1200.0
    rs_coll = {"lend-eth": 900.0, "lend-avax": 300.0}
    idle = {"WETH": 0.0, "USDC": 0.0}
    paused = frozen_rs = False
    if normal:
        if block >= 45_201_830:
            sup[("lend-eth", "WETH")] += 300  # legit large deposit
        if block >= 45_201_850:
            bor[("lend-eth", "WETH")] += 150  # legit large borrow
        if block >= 45_201_860:
            rs_supply += 50
            rs_backing += 50  # legit bridged rsETH, fully backed
    else:
        if block >= FORGED:
            rs_supply += 5000  # forged release: no backing
        if block >= 45_201_814:
            rs_coll["lend-eth"] += 5000
        if respond and block >= REACT:
            for key, amount in treasury.items():
                sup[key] -= amount
                idle[key[1]] += amount
            treasury = {key: 0.0 for key in treasury}
            paused = True
        if not respond:
            for b in (45_201_832, 45_201_836):
                if block >= b:
                    sup[("lend-eth", "WETH")] -= 100  # panicking suppliers withdraw
        for b in range(45_201_818, 45_201_847, 4):
            if block >= b:
                key = ("lend-eth", "WETH")
                bor[key] = min(bor[key] + 100, sup[key])  # attacker borrows chunks of 100 WETH
        frozen_rs = block >= FREEZE
    reserves = []
    for dep in ("lend-eth", "lend-avax"):
        reserves.append(reserve(dep, "USDC", sup[(dep, "USDC")], bor[(dep, "USDC")], collateral=BOT_USDC_COLLATERAL[dep], ltv=8000))
        reserves.append(reserve(dep, "WETH", sup[(dep, "WETH")], bor[(dep, "WETH")], collateral=0.0, ltv=8000))
        reserves.append(reserve(dep, "rsETH", 0.0, 0.0, collateral=rs_coll[dep], ltv=7500, borrowable=False,
                                frozen=frozen_rs and dep == "lend-eth"))
    avail = {(r.deployment_id, r.asset): int(r.available_liquidity) / 10 ** r.decimals for r in reserves}
    positions = [position(d, a, v, avail[(d, a)]) for (d, a), v in treasury.items() if v > 0]
    tokens = [
        TokenSnapshot(symbol="USDC", address=ADDR["USDC"], decimals=6, total_supply=units(50_000_000, "USDC"), price_usd=1.0),
        TokenSnapshot(symbol="WETH", address=ADDR["WETH"], decimals=18, total_supply=units(20_000, "WETH"), price_usd=2500.0),
        TokenSnapshot(symbol="rsETH", address=ADDR["rsETH"], decimals=18, total_supply=units(rs_supply, "rsETH"),
                      backing=units(rs_backing, "WETH"), backing_ratio_bps=int(rs_backing / rs_supply * 10_000), price_usd=2500.0,
                      bridge_source_locked=units(rs_backing, "rsETH"), bridge_destination_released=units(rs_supply, "rsETH"),
                      bridge_source_nonce=307, bridge_destination_nonce=308 if not normal and block >= FORGED else 307,
                      bridge_paused=not normal and block >= FREEZE),
    ]
    vault = VaultStatus(address=VAULT, deposits_paused=paused, idle_balances={s: units(v, s) for s, v in idle.items()})
    return Snapshot(network=NET, chain_id=CHAIN, block_number=block, block_time=t(block), source="fixture",
                    reserves=reserves, tokens=tokens, positions=positions, vault=vault)


def canonical(obj) -> bytes:
    """TASKS.md 2.6 / T4: sorted keys, no spaces, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def khex(data: bytes) -> str:
    return "0x" + keccak(data).hex()


def fake_tx(label: str) -> str:
    return "0x" + keccak(label.encode()).hex()


def dump(name: str, data) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    for name, kw in (("snapshots_attack.jsonl", {"respond": False}), ("snapshots_normal.jsonl", {"respond": False, "normal": True})):
        lines = [world(b, **kw).model_dump_json() for b in range(B0, B0 + 81, 2)]
        (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    at_alert = world(FORGED, respond=True)  # identical to the no-reaction world at this block
    r1 = Alert(
        id=f"ALT-{NET}-{FORGED}-R1_BRIDGE_INVARIANT-global-rsETH", rule_id="R1_BRIDGE_INVARIANT", severity="critical", network=NET,
        deployment_id=None, asset="rsETH", block_number=FORGED, block_time=t(FORGED), detected_at=t(FORGED) + timedelta(seconds=1),
        title="rsETH bridge invariant broken",
        explanation="The rsETH bridge released 5,000 tokens without canonical source backing; destination nonce 308 is ahead of source nonce 307.",
        metrics={"source_locked": 1200.0, "destination_released": 6200.0, "conservation_gap": 5000.0,
                 "source_nonce": 307, "destination_nonce": 308, "exposed_deployments": "lend-eth,lend-avax"},
        exposure_usd=1_325_000.0, rules_version=RULES_V,
    )
    dump("alerts.json", [r1.model_dump(mode="json")])

    executed = t(REACT)
    actions = [
        Action(type="NOTIFY", mode="auto", status="executed", executed_at=t(FORGED) + timedelta(seconds=1), note="channels: log"),
        Action(type="PAUSE_DEPOSITS", mode="auto", status="executed", tx_hash=fake_tx("pause"), executed_at=executed),
    ]
    for dep, asset, amount in POSITIONS:
        actions.append(Action(type="EMERGENCY_WITHDRAW", mode="auto", status="executed", params={"deployment_id": dep, "asset": asset},
                              tx_hash=fake_tx(f"withdraw:{dep}:{asset}"), amount=units(amount, asset), executed_at=executed))
    actions += [
        Action(type="OPEN_INCIDENT", mode="auto", status="executed", executed_at=executed, note="delegated to incident manager"),
        Action(type="UNPAUSE_DEPOSITS", mode="human", status="pending_approval"),
    ]
    inputs = {"alerts": [r1.model_dump(mode="json")], "snapshot": at_alert.model_dump(mode="json")}
    decision = Decision(
        id=f"DEC-{NET}-{FORGED}-1", created_at=t(FORGED) + timedelta(seconds=1), network=NET, block_number=FORGED,
        alert_ids=[r1.id], severity="critical", exposure_usd=1_325_000.0, withdrawable_usd=1_325_000.0, exit_cost_bps=0,
        matrix_cell="critical|exposure>=1k|exit_possible",
        rationale="Critical alert with 1,325,000 USD exposed and full liquidity available: pause deposits and pull every concerned position back to the vault.",
        actions=actions, inputs_hash=khex(canonical(inputs)), rules_version=RULES_V, playbook_version=PLAYBOOK_V,
    )
    decision.record_hash = khex(canonical(decision.model_dump(mode="json", exclude={"record_hash", "anchor_tx", "anchor_block"})))
    decision.anchor_tx, decision.anchor_block = fake_tx("anchor:" + decision.record_hash), REACT + 1
    dump("decisions.json", [decision.model_dump(mode="json")])
    dump("verify.json", VerifyResult(decision_id=decision.id, match=True, stored_hash=decision.record_hash,
                                     recomputed_hash=decision.record_hash, anchored=True, anchor_tx=decision.anchor_tx,
                                     anchor_block=decision.anchor_block).model_dump(mode="json"))

    aware = r1.detected_at
    classified = aware + timedelta(minutes=2)
    initial_due = min(classified + timedelta(hours=4), aware + timedelta(hours=24))
    intermediate_due = initial_due + timedelta(hours=72)
    report = (
        "# DORA initial notification (draft, human review required)\n\n"
        "- Financial entity: Example Treasury SAS (synthetic)\n"
        "- Incident reference: INC-20261011-001\n"
        f"- Detected: {aware.isoformat()}\n"
        f"- Proposed classification: major ({classified.isoformat()}), RTS (EU) 2024/1772 Art. 8(1)(b): critical service affected, "
        "thresholds 9(1) clients and 9(4) geographical spread met\n"
        "- Affected service: on-chain treasury management (critical service)\n"
        "- Description: unbacked rsETH released by a third-party bridge became collateral on a lending protocol where the entity supplies "
        "liquidity. Automated controls paused new deposits and pulled every concerned position back to the vault (1,325,000 USD) "
        "before liquidity ran out.\n"
        "- Status: contained. No client funds lost. Deposits stay paused until the signers reopen them.\n"
        f"- Next report due: intermediate report by {intermediate_due.isoformat()}\n"
    )
    incident = Incident(
        id="INC-20261011-001", title="Unbacked rsETH collateral on lend-eth", status="contained", severity="critical",
        opened_at=t(FORGED) + timedelta(seconds=1), detected_at=aware, contained_at=t(REACT) + timedelta(seconds=2),
        alert_ids=[r1.id], decision_ids=[decision.id], exposure_usd=1_325_000.0, saved_usd=1_325_000.0, at_risk_usd=0.0,
        dora=DoraAssessment(
            criteria=DoraCriteria(critical_services_affected=True, clients_affected_pct=100.0, clients_affected_count=1200,
                                  transactions_affected_value_pct=0.0, duration_hours=0.5, critical_service_downtime_hours=0.5,
                                  member_states_affected=2, reputational_impact=False, data_losses=False,
                                  malicious_unauthorised_access=False, economic_impact_eur=0.0),
            thresholds_met=["9(1)", "9(4)"], is_major=True,
            legal_basis="RTS (EU) 2024/1772 Art. 8(1)(b): critical services affected and two materiality thresholds of Art. 9 met.",
            aware_at=aware, classified_at=classified,
            deadlines=DoraDeadlines(initial_notification_due=initial_due, intermediate_report_due=intermediate_due,
                                    final_report_due=intermediate_due + timedelta(days=30)),
            report_markdown=report, ai_drafted_sections=[],
        ),
        timeline=[
            TimelineEvent(at=t(FORGED), block_number=FORGED, kind="chain", text="5,000 rsETH released without backing"),
            TimelineEvent(at=aware, block_number=FORGED, kind="alert", text="R1_BACKING_DROP (critical): rsETH backing fell to 19.4 %", ref=r1.id),
            TimelineEvent(at=executed, block_number=REACT, kind="action", text="Deposits paused; 250 WETH and 700,000 USDC pulled back to the vault", ref=decision.id),
            TimelineEvent(at=classified, kind="dora", text="Proposed classification: major incident (draft, not sent)"),
            TimelineEvent(at=t(45_201_842), block_number=45_201_842, kind="chain", text="WETH liquidity on lend-eth reaches zero"),
            TimelineEvent(at=t(FREEZE), block_number=FREEZE, kind="chain", text="Protocol guardian freezes rsETH on lend-eth"),
        ],
    )
    dump("incident.json", incident.model_dump(mode="json"))

    now = world(LAST, respond=True)
    dump("state.json", StateResponse(
        network=NET, chain_id=CHAIN, block_number=LAST, block_time=t(LAST), updated_at=t(LAST) + timedelta(seconds=1),
        risk_level="critical", open_incident_id=incident.id, vault=now.vault, positions=now.positions, reserves=now.reserves,
        tokens=now.tokens, totals={"value_usd": 1_325_000.0, "withdrawable_usd": 0.0, "idle_usd": 1_325_000.0, "at_risk_usd": 0.0},
    ).model_dump(mode="json"))
    dump("health.json", Health(status="ok", network=NET, chain_id=CHAIN, block_number=LAST, rpc_ok=True,
                               engine_running=False, version="0.1.0").model_dump(mode="json"))

    series: dict[str, list] = {}
    for dep, asset in (("lend-eth", "WETH"), ("lend-eth", "USDC"), ("lend-avax", "WETH"), ("lend-avax", "USDC")):
        points = []
        for b in range(B0, B0 + 81, 2):
            w = world(b, respond=True)
            r = next(x for x in w.reserves if x.deployment_id == dep and x.asset == asset)
            p = next((x for x in w.positions if x.deployment_id == dep and x.asset == asset), None)
            rs = next(x for x in w.tokens if x.symbol == "rsETH")
            points.append(SeriesPoint(block_number=b, block_time=w.block_time, utilization_bps=r.utilization_bps,
                                      available_liquidity=r.available_liquidity, supply_apy_bps=r.supply_apy_bps,
                                      withdrawable_ratio_bps=p.withdrawable_ratio_bps if p else None,
                                      backing_ratio_bps=rs.backing_ratio_bps).model_dump(mode="json"))
        series[f"{dep}:{asset}"] = points
    dump("series.json", series)

    deps = [
        Dependency(id="rpc-fuji", name="Avalanche Fuji RPC", kind="rpc", provider="RPC provider or public Avalanche node", criticality="critical",
                   supports=["monitoring", "response"], fallback="RPC_FALLBACK_URL", status="ok"),
        Dependency(id="aws-compute", name="AWS EC2 (us-east-1)", kind="cloud", provider="Amazon Web Services", criticality="critical",
                   supports=["monitoring", "response", "dashboard"], fallback="local run (make demo)", status="ok"),
        Dependency(id="aws-sns", name="Amazon SNS alerts", kind="alerting", provider="Amazon Web Services", criticality="important",
                   supports=["alerting"], fallback="webhook", status="ok"),
        Dependency(id="aws-s3", name="Amazon S3 evidence store", kind="cloud", provider="Amazon Web Services", criticality="important",
                   supports=["evidence"], fallback="local data/evidence + on-chain hash", status="ok"),
        Dependency(id="bedrock", name="Amazon Bedrock (Claude)", kind="ai_model", provider="Amazon Web Services", criticality="standard",
                   supports=["report drafting"], fallback="deterministic report template", status="ok"),
        Dependency(id="oracle", name="Price oracle", kind="oracle", provider="MockOracle on the test network", criticality="critical",
                   supports=["exposure valuation"], fallback=None, status="ok"),
        Dependency(id="lend-eth", name="Lending protocol (lend-eth)", kind="protocol", provider="MiniLend, simulated", criticality="critical",
                   supports=["treasury yield"], fallback=None, status="degraded"),
        Dependency(id="lend-avax", name="Lending protocol (lend-avax)", kind="protocol", provider="MiniLend, simulated", criticality="critical",
                   supports=["treasury yield"], fallback=None, status="ok"),
        Dependency(id="rseth", name="rsETH issuer and bridge", kind="bridge", provider="simulated bridge (MockBridge)", criticality="important",
                   supports=["collateral on lending markets"], fallback=None, status="down"),
    ]
    dump("dependencies.json", [d.model_dump(mode="json") for d in deps])

    dump("metrics.json", EvalMetrics(
        generated_at=T0, rules_version=RULES_V,
        synthetic={"runs_attack": 0, "runs_normal": 0, "detection_rate": 0.0, "false_positive_rate": 0.0, "ttd_blocks_p50": -1,
                   "ttd_blocks_p90": -1, "saved_pct_mean": 0.0, "baseline_saved_pct_mean": 0.0},
        notes=["FIXTURE VALUES: T7 replaces them with measured metrics in data/eval/metrics.json."]).model_dump(mode="json"))

    params = {"forged_amount": 5000, "chunk_weth": 100, "interval_s": 8, "bot_withdrawals": 2}
    dump("demo_run.json", DemoRun(run_id="RUN-20261011080000-attack-42", kind="attack", variant="default", seed=42, status="running",
                                  started_at=T0, params=params,
                                  log=["forged_mint ok tx 0x…", "collateral_deposit ok tx 0x…", "borrow 1/6 ok tx 0x…"]).model_dump(mode="json"))
    dump("run_record.example.json", RunRecord(
        run_id="RUN-20261011080000-attack-42", network=NET, label="attack", variant="default", seed=42, params=params,
        start_block=B0, end_block=LAST, attack_start_block=FORGED,
        phase_blocks={"forged_mint": FORGED, "collateral_deposit": 45_201_816, "first_borrow": 45_201_818,
                      "liquidity_zero": 45_201_838, "protocol_freeze": FREEZE},
        treasury_supplied_at_start={f"{d}:{a}": units(v, a) for d, a, v in POSITIONS}).model_dump(mode="json"))
    dump("deployments.example.json", {
        "network": NET, "chain_id": CHAIN, "deployed_at_block": 45_201_700, "explorer": "https://testnet.snowtrace.io",
        "assets": {s: ADDR[s] for s in ("USDC", "WETH", "rsETH")},
        "contracts": {k: ADDR[k] for k in ("MockBridge", "MockOracle", "TreasuryVault", "EvidenceRegistry")},
        "lending": [
            {"id": "lend-eth", "label": "Lending protocol, Ethereum deployment (simulated)", "address": ADDR["lend-eth"]},
            {"id": "lend-avax", "label": "Lending protocol, Avalanche deployment (simulated)", "address": ADDR["lend-avax"]},
        ],
        "roles": {"deployer": "0x…", "owner": "0x…", "guardian": "0x…", "protocol_guardian": "0x…", "attacker": "0x…",
                  "evidence": "0x…", "bots": ["0x…", "0x…", "0x…"]},
    })
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
