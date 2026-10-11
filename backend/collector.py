from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, localcontext

from web3 import Web3
from web3.exceptions import ContractLogicError

from backend import chain, rules, settings
from backend.models import PositionSnapshot, ReserveSnapshot, Snapshot, TokenSnapshot, VaultStatus

log = logging.getLogger("backend.collector")
_decimals: dict[tuple, int] = {}


def clear_caches() -> None:
    _decimals.clear()


def ratio_bps(part: int, whole: int) -> int:
    if part < 0 or whole < 0:
        raise ValueError("Ratio amounts cannot be negative")
    return (part * 10_000 + whole // 2) // whole if whole else 0


def struct_to_dict(abi: list, fn_name: str, value: tuple | Mapping) -> dict:
    functions = [entry for entry in abi if entry.get("type") == "function" and entry.get("name") == fn_name]
    if len(functions) != 1:
        raise ValueError(f"Ambiguous or missing ABI function: {fn_name}")
    outputs = functions[0].get("outputs", [])
    components = outputs[0].get("components", []) if len(outputs) == 1 else []
    names = [component.get("name") for component in components]
    if not names or not all(names) or len(set(names)) != len(names) or len(value) != len(names):
        raise ValueError("Reserve tuple does not match ABI components")
    if isinstance(value, Mapping):
        if set(value) != set(names):
            raise ValueError("Reserve fields do not match ABI")
        return dict(value)
    return dict(zip(names, value, strict=True))


def _uint(value: int) -> int:
    if type(value) is not int or not 0 <= value < 2**256:
        raise ValueError("Contract returned an invalid uint256")
    return value


def _usd(amount: int, decimals: int, price_e8: int) -> float:
    with localcontext() as context:
        context.prec = 110
        return float((Decimal(amount) * Decimal(price_e8) / Decimal(10**(decimals + 8))).quantize(Decimal("0.01")))


def _configure_poa(client) -> None:
    onion = getattr(client, "middleware_onion", None)
    if onion is not None and "t3-poa" not in onion:
        try:
            from web3.middleware import ExtraDataToPOAMiddleware as middleware
        except ImportError:
            from web3.middleware import geth_poa_middleware as middleware
        onion.inject(middleware, name="t3-poa", layer=0)


def build_snapshot(block_number: int, client=None) -> Snapshot:
    _uint(block_number)
    client = chain.w3() if client is None else client
    _configure_poa(client)
    dep = chain.load_deployment()
    chain_id = int(client.eth.chain_id)
    if (chain_id != settings.CHAIN_ID or dep["chain_id"] != chain_id or dep["network"] != settings.NETWORK):
        raise ValueError("Deployment, settings and RPC chain identity must agree")
    if dep.get("deployed_at_block", 0) > block_number:
        raise ValueError("Requested block predates the deployment")
    assets = {symbol: Web3.to_checksum_address(address) for symbol, address in dep["assets"].items()}
    by_address = {address.lower(): symbol for symbol, address in assets.items()}
    if len(assets) != len(by_address):
        raise ValueError("Duplicate asset addresses in deployment")
    vault_address = Web3.to_checksum_address(dep["contracts"]["TreasuryVault"])
    first = client.eth.get_block(block_number)
    if first["number"] != block_number or not first.get("hash"):
        raise ValueError("RPC did not return the requested mined block")
    stamp = _uint(first["timestamp"])

    def contract(name, address):
        abi = chain.load_abi(name)
        return client.eth.contract(address=Web3.to_checksum_address(address), abi=abi), abi

    def call(obj, name, *args):
        return getattr(obj.functions, name)(*args).call(block_identifier=block_number)

    oracle, _ = contract("MockOracle", dep["contracts"]["MockOracle"])
    vault, _ = contract("TreasuryVault", vault_address)
    bridge, bridge_abi = contract("MockBridge", dep["contracts"]["MockBridge"])
    bridge_functions = {entry.get("name") for entry in bridge_abi if entry.get("type") == "function"}
    metadata, tokens, pending_cache = {}, [], {}
    deployment_key = (chain_id, dep.get("deployed_at_block"), vault_address)
    for symbol, address in assets.items():
        obj, _ = contract("RsETH" if symbol == "rsETH" else "MockERC20", address)
        cache_key = (*deployment_key, address)
        decimals = _decimals.get(cache_key)
        if decimals is None:
            decimals = _uint(call(obj, "decimals"))
            if decimals > 77:
                raise ValueError("Unsupported token decimals")
            pending_cache[cache_key] = decimals
        try:
            price_e8 = _uint(call(oracle, "getPriceE8", address))
        except ContractLogicError as exc:
            if "Oracle: no price" not in str(exc):
                raise
            price_e8 = 0
            log.warning("Missing oracle price for a configured asset; coverage is degraded")
        metadata[symbol] = (obj, decimals, price_e8)
        tokens.append(TokenSnapshot(symbol=symbol, address=address, decimals=decimals,
                                    total_supply=str(_uint(call(obj, "totalSupply"))), price_usd=price_e8 / 10**8))

    rseth = next((t for t in tokens if t.symbol == "rsETH"), None)
    if rseth is not None:
        for function, field in (("sourceLocked", "bridge_source_locked"), ("destinationReleased", "bridge_destination_released"),
                                ("sourceNonce", "bridge_source_nonce"), ("destinationNonce", "bridge_destination_nonce")):
            if function in bridge_functions:
                value = _uint(call(bridge, function))
                setattr(rseth, field, str(value) if field.endswith(("locked", "released")) else value)
        if "paused" in bridge_functions:
            paused = call(bridge, "paused")
            if type(paused) is not bool:
                raise ValueError("Invalid bridge pause state")
            rseth.bridge_paused = paused
        rseth.backing = rseth.bridge_source_locked
        if rseth.backing is None and "totalBacking" in bridge_functions:
            rseth.backing = str(_uint(call(bridge, "totalBacking")))
        if "backingRatioBps" in bridge_functions:
            rseth.backing_ratio_bps = _uint(call(bridge, "backingRatioBps"))
        elif rseth.bridge_source_locked is not None and rseth.bridge_destination_released is not None:
            released = int(rseth.bridge_destination_released)
            rseth.backing_ratio_bps = int(rseth.bridge_source_locked) * 10_000 // released if released else 10_000

    reserves, positions = [], []
    for deployment in dep["lending"]:
        market, abi = contract("MiniLend", deployment["address"])
        rows = call(market, "getReservesData")
        known_reserves = set()
        for row in rows:
            data = struct_to_dict(abi, "getReservesData", row)
            symbol = by_address.get(data["asset"].lower())
            if symbol is None:
                log.warning("Unknown reserve asset omitted from configured monitoring scope")
                continue
            known_reserves.add(symbol)
            _, decimals, price_e8 = metadata[symbol]
            for name in ("totalSupplied", "totalBorrowed", "availableLiquidity", "totalCollateral", "utilizationBps",
                         "supplyRateBps", "borrowRateBps", "ltvBps"):
                _uint(data[name])
            if data["availableLiquidity"] != data["totalSupplied"] - data["totalBorrowed"]:
                raise ValueError("MiniLend returned inconsistent liquidity accounting")
            for name in ("borrowable", "frozen", "paused"):
                if type(data[name]) is not bool:
                    raise ValueError("Invalid reserve state flag")
            r = ReserveSnapshot(deployment_id=deployment["id"], asset=symbol, asset_address=assets[symbol], decimals=decimals,
                                total_supplied=str(data["totalSupplied"]), total_borrowed=str(data["totalBorrowed"]),
                                available_liquidity=str(data["availableLiquidity"]), total_collateral=str(data["totalCollateral"]),
                                utilization_bps=data["utilizationBps"], supply_apy_bps=data["supplyRateBps"],
                                borrow_apy_bps=data["borrowRateBps"], ltv_bps=data["ltvBps"], borrowable=data["borrowable"],
                                frozen=data["frozen"], paused=data["paused"], price_usd=price_e8 / 10**8)
            reserves.append(r)
            supplied = _uint(call(market, "getUserSupplied", vault_address, assets[symbol]))
            if supplied:
                withdrawable = 0 if r.paused else min(supplied, data["availableLiquidity"])
                positions.append(PositionSnapshot(wallet=vault_address, deployment_id=r.deployment_id, asset=symbol,
                                                   supplied=str(supplied), withdrawable_now=str(withdrawable),
                                                   withdrawable_ratio_bps=ratio_bps(withdrawable, supplied),
                                                   value_usd=_usd(supplied, decimals, price_e8),
                                                   withdrawable_usd=_usd(withdrawable, decimals, price_e8)))
        if known_reserves != set(assets):
            raise ValueError("Configured MiniLend inventory is incomplete")
    deposits_paused = call(vault, "depositsPaused")
    if type(deposits_paused) is not bool:
        raise ValueError("Invalid treasury pause state")
    idle = {symbol: str(_uint(call(obj, "balanceOf", vault_address))) for symbol, (obj, _, _) in metadata.items()}
    last = client.eth.get_block(block_number)
    if last["hash"] != first["hash"] or last["timestamp"] != stamp or last["number"] != block_number:
        raise ValueError("Canonical block changed during snapshot collection")
    snapshot = Snapshot(network=settings.NETWORK, chain_id=chain_id, block_number=block_number,
                        block_time=datetime.fromtimestamp(stamp, timezone.utc), source="live", reserves=reserves,
                        tokens=tokens, positions=positions,
                        vault=VaultStatus(address=vault_address, deposits_paused=deposits_paused, idle_balances=idle))
    rules.validate_snapshot(snapshot)
    if len(_decimals) + len(pending_cache) > 256:
        clear_caches()
    _decimals.update(pending_cache)
    return snapshot


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--block", type=int)
    args = parser.parse_args(argv)
    try:
        client = chain.w3()
        block = args.block if args.block is not None else client.eth.block_number
        print(build_snapshot(block, client).model_dump_json(indent=2))
    except Exception as exc:
        parser.exit(1, f"Snapshot collection failed ({type(exc).__name__}); check network, deployment and ABI configuration.\n")


if __name__ == "__main__":
    main()
