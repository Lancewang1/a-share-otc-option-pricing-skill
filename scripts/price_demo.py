#!/usr/bin/env python3
"""Transparent, standard-library demo for an indicative European equity-option quote."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Literal


OptionType = Literal["call", "put"]
Settlement = Literal["local", "quanto", "composite"]


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class Inputs:
    spot: float = 100.0
    strike: float = 100.0
    days: int = 90
    rate: float = 0.018
    dividend: float = 0.80
    dividend_day: int = 45
    borrow_bps: float = 300.0
    vol: float = 0.28
    option_type: OptionType = "call"
    notional: float = 1_000_000.0
    settlement: Settlement = "local"
    fx_vol: float = 0.06
    equity_fx_corr: float = -0.20
    hedge_bps: float = 8.0
    credit_bps_pa: float = 35.0
    capital_bps_pa: float = 25.0
    half_spread_vol_points: float = 1.0


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega_per_point: float
    theta_per_day: float
    rho_per_point: float


def validate(i: Inputs) -> None:
    if i.spot <= 0 or i.strike <= 0:
        raise ValueError("spot and strike must be positive")
    if i.days <= 0:
        raise ValueError("days must be positive")
    if i.vol <= 0 or i.fx_vol < 0:
        raise ValueError("vol must be positive and fx_vol non-negative")
    if i.notional <= 0:
        raise ValueError("notional must be positive")
    if not -1 <= i.equity_fx_corr <= 1:
        raise ValueError("equity_fx_corr must be between -1 and 1")
    if i.dividend < 0 or i.dividend_day < 0:
        raise ValueError("dividend and dividend_day must be non-negative")


def dividend_pv(i: Inputs) -> float:
    if i.dividend == 0 or i.dividend_day > i.days:
        return 0.0
    return i.dividend * math.exp(-i.rate * i.dividend_day / 365.0)


def equity_forward(i: Inputs) -> tuple[float, float]:
    pv = dividend_pv(i)
    ex_div_spot = i.spot - pv
    if ex_div_spot <= 0:
        raise ValueError("present value of dividends must be below spot")
    t = i.days / 365.0
    borrow = i.borrow_bps / 10_000.0
    return ex_div_spot * math.exp((i.rate - borrow) * t), pv


def settlement_terms(i: Inputs) -> tuple[float, float, float]:
    """Return pricing rate, pricing volatility, and quanto drift adjustment.

    equity_fx_corr is corr(equity return, settlement-currency-per-CNY return).
    """
    if i.settlement == "local":
        return i.rate, i.vol, 0.0
    if i.settlement == "quanto":
        drift_adjustment = -i.equity_fx_corr * i.vol * i.fx_vol
        return i.rate + drift_adjustment, i.vol, drift_adjustment
    combined_variance = (
        i.vol * i.vol
        + i.fx_vol * i.fx_vol
        + 2.0 * i.equity_fx_corr * i.vol * i.fx_vol
    )
    if combined_variance <= 0:
        raise ValueError("composite variance must be positive")
    return i.rate, math.sqrt(combined_variance), 0.0


def black_scholes(
    spot: float,
    strike: float,
    t: float,
    rate: float,
    carry_yield: float,
    vol: float,
    option_type: OptionType,
) -> tuple[float, Greeks]:
    cp = 1.0 if option_type == "call" else -1.0
    root_t = math.sqrt(t)
    vol_t = vol * root_t
    d1 = (math.log(spot / strike) + (rate - carry_yield + 0.5 * vol * vol) * t) / vol_t
    d2 = d1 - vol_t
    df_q = math.exp(-carry_yield * t)
    df_r = math.exp(-rate * t)
    price = cp * (spot * df_q * norm_cdf(cp * d1) - strike * df_r * norm_cdf(cp * d2))
    delta = cp * df_q * norm_cdf(cp * d1)
    gamma = df_q * norm_pdf(d1) / (spot * vol_t)
    vega = spot * df_q * norm_pdf(d1) * root_t / 100.0
    theta = (
        -spot * df_q * norm_pdf(d1) * vol / (2.0 * root_t)
        - cp * rate * strike * df_r * norm_cdf(cp * d2)
        + cp * carry_yield * spot * df_q * norm_cdf(cp * d1)
    ) / 365.0
    rho = cp * strike * t * df_r * norm_cdf(cp * d2) / 100.0
    return price, Greeks(delta, gamma, vega, theta, rho)


def calculate(i: Inputs) -> dict:
    validate(i)
    t = i.days / 365.0
    forward, pv_dividend = equity_forward(i)
    carry_yield = i.rate - math.log(forward / i.spot) / t
    pricing_rate, pricing_vol, drift_adjustment = settlement_terms(i)
    price, greeks = black_scholes(
        i.spot, i.strike, t, pricing_rate, carry_yield, pricing_vol, i.option_type
    )

    theoretical_pct = price / i.spot
    hedge_pct = i.hedge_bps / 10_000.0
    credit_pct = i.credit_bps_pa / 10_000.0 * t
    capital_pct = i.capital_bps_pa / 10_000.0 * t
    spread_pct = i.half_spread_vol_points * greeks.vega_per_point / i.spot
    quote_pct = theoretical_pct + hedge_pct + credit_pct + capital_pct + spread_pct

    call, _ = black_scholes(i.spot, i.strike, t, pricing_rate, carry_yield, pricing_vol, "call")
    put, _ = black_scholes(i.spot, i.strike, t, pricing_rate, carry_yield, pricing_vol, "put")
    parity_rhs = i.spot * math.exp(-carry_yield * t) - i.strike * math.exp(-pricing_rate * t)

    return {
        "status": "INDICATIVE",
        "inputs": asdict(i),
        "curve": {
            "time_years": t,
            "dividend_pv": pv_dividend,
            "forward_local": forward,
            "implied_carry_yield": carry_yield,
        },
        "settlement": {
            "type": i.settlement,
            "pricing_rate": pricing_rate,
            "pricing_vol": pricing_vol,
            "quanto_drift_adjustment": drift_adjustment,
        },
        "theoretical": {
            "price_per_share": price,
            "percent_of_notional": theoretical_pct,
            "greeks": asdict(greeks),
        },
        "waterfall": {
            "theoretical_pct": theoretical_pct,
            "hedge_pct": hedge_pct,
            "credit_pct": credit_pct,
            "capital_pct": capital_pct,
            "half_spread_pct": spread_pct,
            "client_buy_quote_pct": quote_pct,
            "premium": quote_pct * i.notional,
        },
        "checks": {
            "put_call_parity_error": (call - put) - parity_rhs,
            "positive_price": price >= 0,
            "dividend_pv_below_spot": pv_dividend < i.spot,
        },
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spot", type=float, default=100.0)
    p.add_argument("--strike", type=float, default=100.0)
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--rate", type=float, default=0.018, help="decimal annual rate")
    p.add_argument("--dividend", type=float, default=0.80, help="one cash dividend per share")
    p.add_argument("--dividend-day", type=int, default=45)
    p.add_argument("--borrow-bps", type=float, default=300.0)
    p.add_argument("--vol", type=float, default=0.28, help="decimal annual volatility")
    kind = p.add_mutually_exclusive_group()
    kind.add_argument("--call", dest="option_type", action="store_const", const="call")
    kind.add_argument("--put", dest="option_type", action="store_const", const="put")
    p.set_defaults(option_type="call")
    p.add_argument("--notional", type=float, default=1_000_000.0)
    p.add_argument("--settlement", choices=("local", "quanto", "composite"), default="local")
    p.add_argument("--fx-vol", type=float, default=0.06)
    p.add_argument("--equity-fx-corr", type=float, default=-0.20)
    p.add_argument("--hedge-bps", type=float, default=8.0)
    p.add_argument("--credit-bps-pa", type=float, default=35.0)
    p.add_argument("--capital-bps-pa", type=float, default=25.0)
    p.add_argument("--half-spread-vol-points", type=float, default=1.0)
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return p


def main() -> None:
    args = parser().parse_args()
    emit_json = args.json
    delattr(args, "json")
    result = calculate(Inputs(**vars(args)))
    if emit_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    c = result["curve"]
    s = result["settlement"]
    th = result["theoretical"]
    w = result["waterfall"]
    g = th["greeks"]
    print("INDICATIVE A-share OTC option demo")
    print(f"Forward: {c['forward_local']:.6f} | dividend PV: {c['dividend_pv']:.6f} | q0: {c['implied_carry_yield']:.4%}")
    print(f"Settlement: {s['type']} | pricing vol: {s['pricing_vol']:.4%} | pricing rate: {s['pricing_rate']:.4%}")
    print(f"Theoretical: {th['price_per_share']:.6f} per share ({th['percent_of_notional']:.4%} of notional)")
    print(f"Delta {g['delta']:.6f} | Gamma {g['gamma']:.6f} | Vega/1pt {g['vega_per_point']:.6f} | Theta/day {g['theta_per_day']:.6f}")
    print(f"Client-buy quote: {w['client_buy_quote_pct']:.4%} | premium: {w['premium']:,.2f}")
    print(f"Put-call parity error: {result['checks']['put_call_parity_error']:.3e}")


if __name__ == "__main__":
    main()
