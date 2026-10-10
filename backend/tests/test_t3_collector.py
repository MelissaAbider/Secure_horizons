import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from web3.exceptions import ContractLogicError

from backend import chain, collector, settings
from backend.models import Snapshot
from backend.tests.test_t3_rules import load_series


FIELDS = [
    ("asset", "address", "asset_address"),
    ("totalSupplied", "uint256", "total_supplied"),
    ("totalBorrowed", "uint256", "total_borrowed"),
    ("availableLiquidity", "uint256", "available_liquidity"),
    ("utilizationBps", "uint256", "utilization_bps"),
    ("supplyRateBps", "uint256", "supply_apy_bps"),
    ("borrowRateBps", "uint256", "borrow_apy_bps"),
    ("totalCollateral", "uint256", "total_collateral"),
    ("ltvBps", "uint16", "ltv_bps"),
    ("borrowable", "bool", "borrowable"),
    ("frozen", "bool", "frozen"),
    ("paused", "bool", "paused"),
]


def abi_function(name, outputs=None):
    return {"type": "function", "name": name, "stateMutability": "view", "inputs": [],
            "outputs": outputs or [{"name": "", "type": "uint256"}]}


class FakeChain:
    def __init__(self, snapshot):
        self.snapshot = snapshot.model_copy(deep=True)
        self.dep = json.loads((Path(__file__).resolve().parents[2] / "fixtures/deployments.example.json").read_text())
        self.dep["network"] = snapshot.network
        self.dep["chain_id"] = snapshot.chain_id
        components = [{"name": n, "type": t} for n, t, _ in FIELDS]
        self.abis = {
            "MiniLend": [abi_function("getReservesData", [{"name": "", "type": "tuple[]", "components": components}]), abi_function("getUserSupplied")],
            "MockERC20": [abi_function(n) for n in ("decimals", "totalSupply", "balanceOf")],
            "RsETH": [abi_function(n) for n in ("decimals", "totalSupply", "balanceOf")],
            "MockOracle": [abi_function("getPriceE8")],
            "TreasuryVault": [abi_function("depositsPaused")],
            "MockBridge": [abi_function(n) for n in ("sourceLocked", "destinationReleased", "sourceNonce", "destinationNonce", "paused")],
        }
        self.eth = self
        self.chain_id = snapshot.chain_id
        self.block_number = snapshot.block_number
        self.calls = []
        self.headers = 0
        self.reorg = False
        self.fail_function = None
        self.missing_price = None

    def install(self, monkeypatch):
        monkeypatch.setattr(chain, "load_deployment", lambda: copy.deepcopy(self.dep))
        monkeypatch.setattr(chain, "load_abi", lambda name: copy.deepcopy(self.abis[name]))
        monkeypatch.setattr(chain, "w3", lambda: self)
        monkeypatch.setattr(settings, "CHAIN_ID", self.chain_id)
        monkeypatch.setattr(settings, "NETWORK", self.snapshot.network)
        collector.clear_caches()

    def get_block(self, block):
        assert block == self.snapshot.block_number
        self.headers += 1
        return {"number": block, "timestamp": int(self.snapshot.block_time.timestamp()),
                "hash": bytes([2 if self.reorg and self.headers > 1 else 1]) * 32}

    def contract(self, address, abi):
        owner = self

        class Functions:
            def __getattr__(self, name):
                def build(*args):
                    def call(*, block_identifier):
                        owner.calls.append((address.lower(), name, args, block_identifier))
                        assert block_identifier == owner.snapshot.block_number
                        if name == owner.fail_function:
                            raise ConnectionError("rpc unavailable")
                        return owner.value(address, name, args)
                    return SimpleNamespace(call=call)
                return build

        return SimpleNamespace(functions=Functions())

    def value(self, address, name, args):
        s, dep = self.snapshot, self.dep
        address = address.lower()
        tokens = {t.address.lower(): t for t in s.tokens}
        if address in tokens:
            t = tokens[address]
            return {"decimals": t.decimals, "totalSupply": int(t.total_supply),
                    "balanceOf": int(s.vault.idle_balances.get(t.symbol, "0"))}[name]
        if address == dep["contracts"]["MockOracle"].lower():
            t = tokens[args[0].lower()]
            if t.symbol == self.missing_price:
                raise ContractLogicError("execution reverted: Oracle: no price")
            return int(t.price_usd * 10**8)
        if address == dep["contracts"]["TreasuryVault"].lower():
            return s.vault.deposits_paused
        if address == dep["contracts"]["MockBridge"].lower():
            t = next(t for t in s.tokens if t.symbol == "rsETH")
            return {"sourceLocked": int(t.bridge_source_locked), "destinationReleased": int(t.bridge_destination_released),
                    "sourceNonce": t.bridge_source_nonce, "destinationNonce": t.bridge_destination_nonce,
                    "paused": t.bridge_paused, "totalBacking": int(t.backing), "backingRatioBps": t.backing_ratio_bps}[name]
        deployment = next(d["id"] for d in dep["lending"] if d["address"].lower() == address)
        if name == "getReservesData":
            return [tuple(int(getattr(r, field)) if typ.startswith("uint") else getattr(r, field)
                          for _, typ, field in FIELDS) for r in s.reserves if r.deployment_id == deployment]
        assert args[0].lower() == s.vault.address.lower()
        return next((int(p.supplied) for p in s.positions
                     if p.deployment_id == deployment and tokens[args[1].lower()].symbol == p.asset), 0)


@pytest.fixture
def rpc(monkeypatch):
    fake = FakeChain(load_series("snapshots_attack.jsonl")[0])
    fake.install(monkeypatch)
    return fake


def test_collect_pins_all_reads_and_matches_initial_positions(rpc):
    s = collector.build_snapshot(rpc.block_number, rpc)
    assert s.source == "live"
    assert len(s.reserves) == 6
    assert len(s.positions) == 4
    assert sum(p.value_usd for p in s.positions) == 1_325_000
    assert all(p.withdrawable_ratio_bps == 10_000 for p in s.positions)
    assert all(c[3] == rpc.block_number for c in rpc.calls)
    assert sum(c[1] == "getReservesData" for c in rpc.calls) == 2
    assert rpc.headers == 2
    assert next(t for t in s.tokens if t.symbol == "rsETH").bridge_source_nonce == 307


def test_collect_handles_pause_but_does_not_block_freeze(rpc):
    r = next(r for r in rpc.snapshot.reserves if r.deployment_id == "lend-eth" and r.asset == "WETH")
    r.frozen = True
    s = collector.build_snapshot(rpc.block_number, rpc)
    assert next(p for p in s.positions if p.deployment_id == "lend-eth" and p.asset == "WETH").withdrawable_ratio_bps == 10_000
    r.paused = True
    s = collector.build_snapshot(rpc.block_number, rpc)
    p = next(p for p in s.positions if p.deployment_id == "lend-eth" and p.asset == "WETH")
    assert p.withdrawable_now == "0"
    assert p.withdrawable_usd == 0


def test_positions_survive_borrowable_flag_change(rpc):
    next(r for r in rpc.snapshot.reserves if r.deployment_id == "lend-eth" and r.asset == "WETH").borrowable = False
    assert len(collector.build_snapshot(rpc.block_number, rpc).positions) == 4


def test_missing_optional_bridge_abi_is_unknown_not_fabricated(rpc):
    rpc.abis["MockBridge"] = [abi_function("totalBacking"), abi_function("backingRatioBps")]
    s = collector.build_snapshot(rpc.block_number, rpc)
    t = next(t for t in s.tokens if t.symbol == "rsETH")
    assert t.backing_ratio_bps == 10_000
    assert t.bridge_source_nonce is None
    assert t.bridge_source_locked is None
    assert t.bridge_paused is None


def test_rpc_failure_never_returns_partial_snapshot(rpc):
    rpc.fail_function = "getUserSupplied"
    with pytest.raises(ConnectionError):
        collector.build_snapshot(rpc.block_number, rpc)


def test_reorg_during_collection_discards_snapshot(rpc):
    rpc.reorg = True
    with pytest.raises(ValueError, match="block changed"):
        collector.build_snapshot(rpc.block_number, rpc)


def test_deployment_and_rpc_chain_mismatch_rejected(rpc):
    rpc.chain_id = 1
    with pytest.raises(ValueError, match="chain"):
        collector.build_snapshot(rpc.block_number, rpc)


def test_missing_price_is_zero_with_coverage_issue(rpc):
    rpc.missing_price = "WETH"
    s = collector.build_snapshot(rpc.block_number, rpc)
    assert next(t for t in s.tokens if t.symbol == "WETH").price_usd == 0
    from backend.rules import evaluate_snapshot, load_rules
    assert any("price" in issue.lower() for issue in evaluate_snapshot([s], load_rules()).issues)


def test_decimals_are_cached_only_for_same_deployment(rpc):
    collector.build_snapshot(rpc.block_number, rpc)
    count = sum(c[1] == "decimals" for c in rpc.calls)
    collector.build_snapshot(rpc.block_number, rpc)
    assert sum(c[1] == "decimals" for c in rpc.calls) == count
    rpc.dep["deployed_at_block"] += 1
    collector.build_snapshot(rpc.block_number, rpc)
    assert sum(c[1] == "decimals" for c in rpc.calls) == count * 2


@pytest.mark.parametrize("part,whole,result", [(100 * 10**18, 150 * 10**18, 6667), (0, 5, 0), (5, 0, 0), (150, 150, 10000)])
def test_ratio_bps(part, whole, result):
    assert collector.ratio_bps(part, whole) == result


def test_abi_field_names_drive_mapping(rpc):
    abi = rpc.abis["MiniLend"]
    abi[0]["outputs"][0]["components"] = list(reversed(abi[0]["outputs"][0]["components"]))
    assert collector.struct_to_dict(abi, "getReservesData", tuple(range(12)))["asset"] == 11
    with pytest.raises(ValueError):
        collector.struct_to_dict(abi, "getReservesData", (1, 2))


def test_collector_cli_json(rpc, capsys):
    collector.main(["--once", "--block", str(rpc.block_number)])
    s = Snapshot.model_validate_json(capsys.readouterr().out)
    assert s.block_number == rpc.block_number


def test_incomplete_market_inventory_is_rejected(rpc):
    rpc.snapshot.reserves = [r for r in rpc.snapshot.reserves if not (r.deployment_id == "lend-eth" and r.asset == "USDC")]
    with pytest.raises(ValueError, match="inventory"):
        collector.build_snapshot(rpc.block_number, rpc)


def test_inconsistent_minilend_accounting_is_rejected(rpc):
    rpc.snapshot.reserves[0].available_liquidity = "1"
    with pytest.raises(ValueError, match="liquidity"):
        collector.build_snapshot(rpc.block_number, rpc)


def test_missing_bridge_function_execution_is_not_swallowed(rpc):
    rpc.fail_function = "sourceNonce"
    with pytest.raises(ConnectionError):
        collector.build_snapshot(rpc.block_number, rpc)


def test_cli_failure_does_not_print_provider_secrets(rpc, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ConnectionError("https://user:secret@example.invalid/?key=secret")

    monkeypatch.setattr(collector, "build_snapshot", fail)
    with pytest.raises(SystemExit) as exc:
        collector.main(["--once"])
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert "secret" not in output.err
    assert not output.out


def test_poa_middleware_is_compatible_with_installed_web3():
    from web3 import Web3
    client = Web3()
    collector._configure_poa(client)
    collector._configure_poa(client)
    assert "t3-poa" in client.middleware_onion


def test_live_anvil_read_only():
    if os.environ.get("T3_LIVE") != "1":
        pytest.skip("Set T3_LIVE=1 with deployed and seeded local contracts to run the read-only check")
    s = collector.build_snapshot(chain.w3().eth.block_number)
    assert s.chain_id == settings.CHAIN_ID
    assert s.source == "live"
    assert len(s.positions) == 4
    assert sum(p.value_usd for p in s.positions) == 1_325_000
