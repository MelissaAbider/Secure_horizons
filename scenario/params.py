"""Attack and normal-traffic parameters (TASKS.md T2 step 2). Owner: T2. Pure: no chain access.

seed = 0: the exact default parameters. seed >= 1: a deterministic draw from random.Random(seed).
The draw ranges below are the only reference: nothing here looks at the detection thresholds.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Optional

from backend import settings

VARIANTS = ("default", "slow", "usdc")
BASE_INTERVAL_S = {"fuji": 8.0, "local": 1.0}
NORMAL_TICK_S = {"fuji": 6.0, "local": 1.0}


@dataclass(frozen=True)
class AttackParams:
    variant: str
    seed: int
    market: str
    forged_amount: int  # rsETH, human units
    drain_asset: str  # "WETH" | "USDC"
    chunk: int  # human units of drain_asset
    interval_s: float
    warmup_s: float
    gap_s: float
    freeze_delay_s: float
    cooldown_s: float
    withdraw_after: tuple[int, ...]  # 1-based borrow indexes after which a bot withdraws
    bot_withdraw_amount: int  # human units of drain_asset
    max_chunks: int = 200

    def as_params(self) -> dict[str, str | int | float | bool]:
        weth = self.drain_asset == "WETH"
        return {
            "forged_amount": self.forged_amount,
            "chunk_weth": self.chunk if weth else 0,
            "interval_s": self.interval_s,
            "bot_withdrawals": len(self.withdraw_after),
            "drain_asset": self.drain_asset,
            "chunk_usdc": 0 if weth else self.chunk,
            "withdraw_after": ",".join(str(i) for i in self.withdraw_after),
            "bot_withdraw_amount": self.bot_withdraw_amount,
        }

    def with_timing(self, interval_s: Optional[float] = None, warmup_s: Optional[float] = None,
                    freeze_delay_s: Optional[float] = None) -> "AttackParams":
        """CLI and test overrides, applied after the draw. A new interval re-derives the other delays."""
        p = self if interval_s is None else replace(self, **_timing(interval_s))
        if warmup_s is not None:
            p = replace(p, warmup_s=warmup_s)
        if freeze_delay_s is not None:
            p = replace(p, freeze_delay_s=freeze_delay_s)
        return p


def _timing(interval_s: float) -> dict[str, float]:
    return {"interval_s": interval_s, "warmup_s": round(3 * interval_s, 1), "gap_s": interval_s,
            "freeze_delay_s": round(10 * interval_s, 1), "cooldown_s": interval_s}


def _round_up_100(x: int) -> int:
    return max(100, (x + 50) // 100 * 100)


def attack_params(variant: str = "default", seed: int = 0, network: Optional[str] = None) -> AttackParams:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r} (expected one of {', '.join(VARIANTS)})")
    if seed < 0:
        raise ValueError("seed must be >= 0")
    base = BASE_INTERVAL_S.get(network or settings.NETWORK, BASE_INTERVAL_S["local"])
    interval = base * 3 if variant == "slow" else base
    if variant == "usdc":
        asset, chunk, after, bot_amount = "USDC", 250_000, (2, 3), 250_000
    elif variant == "slow":
        asset, chunk, after, bot_amount = "WETH", 25, (12, 20), 100
    else:
        asset, chunk, after, bot_amount = "WETH", 100, (4, 5), 100
    forged = 5_000

    if seed >= 1:
        rng = random.Random(seed)
        forged = rng.randrange(3_000, 8_001, 500)
        if variant == "usdc":
            chunk = rng.choice((100_000, 250_000, 400_000))
        elif variant == "slow":
            chunk = rng.choice((10, 25, 40))
        else:
            chunk = rng.choice((50, 100, 150, 200))
        interval = round(interval * rng.uniform(0.75, 1.25), 1)
        after = tuple(sorted(rng.sample(range(2, 8), rng.randint(1, 3))))
        bot_amount = 250_000 if asset == "USDC" else _round_up_100(chunk)

    return AttackParams(variant=variant, seed=seed, market="lend-eth", forged_amount=forged, drain_asset=asset,
                        chunk=chunk, withdraw_after=after, bot_withdraw_amount=bot_amount, **_timing(interval))


@dataclass(frozen=True)
class NormalParams:
    minutes: float
    seed: int
    tick_s: float
    ticks: int

    def as_params(self) -> dict[str, str | int | float | bool]:
        return {"minutes": self.minutes, "seed": self.seed, "tick_s": self.tick_s, "ticks": self.ticks}


def normal_params(minutes: float, seed: int = 0, network: Optional[str] = None, ticks: Optional[int] = None,
                  tick_s: Optional[float] = None) -> NormalParams:
    if tick_s is None:
        tick_s = NORMAL_TICK_S.get(network or settings.NETWORK, NORMAL_TICK_S["local"])
    if ticks is None:
        ticks = int(minutes * 60 / tick_s) if tick_s > 0 else int(minutes * 60)
    return NormalParams(minutes=minutes, seed=seed, tick_s=tick_s, ticks=ticks)
