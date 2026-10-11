"""Fuji only: sends test AVAX from the deployer to every role that has less than --amount (TASKS.md T1). Owner: T1.

Run from the repo root: make fund-roles AMOUNT=0.01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eth_account import Account  # noqa: E402

from backend import chain, settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--amount", type=float, default=0.01, help="AVAX each role should hold at least")
    amount = parser.parse_args().amount
    if settings.NETWORK == "local":
        sys.exit("fund-roles is for fuji: on local, anvil accounts already hold test ETH")
    w3 = chain.w3()
    deployer = chain.account("deployer")
    target = w3.to_wei(amount, "ether")
    roles = {r: Account.from_key(settings.private_key(r)).address
             for r in ("owner", "guardian", "protocol_guardian", "attacker", "evidence")}
    roles |= {f"bot{i}": Account.from_key(k).address for i, k in enumerate(settings.bot_pks())}
    print(f"deployer {deployer.address}: {w3.from_wei(w3.eth.get_balance(deployer.address), 'ether')} AVAX")
    for role, addr in roles.items():
        missing = target - w3.eth.get_balance(addr)
        if missing <= 0:
            print(f"  {role:18s} {addr} ok")
            continue
        tx = {"to": addr, "value": missing, "gas": 21_000, "gasPrice": w3.eth.gas_price,
              "nonce": w3.eth.get_transaction_count(deployer.address, "pending"), "chainId": settings.CHAIN_ID}
        signed = deployer.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(getattr(signed, "raw_transaction", None) or signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  {role:18s} {addr} +{w3.from_wei(missing, 'ether')} AVAX  {chain.explorer_tx(w3.to_hex(tx_hash))}")


if __name__ == "__main__":
    main()
