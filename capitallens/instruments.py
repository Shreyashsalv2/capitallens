"""Instrument pricing and scenario P&L.

Two kinds of position:
  linear  - delta-one exposure (FX spot/forwards, commodity futures). P&L = notional_usd * return.
  option  - European call/put on a spot factor, priced with Black's formula at zero rates.
            Each scenario is fully revalued, so gamma and the option's kink are captured.
Simplifications (documented in the README): zero interest rates, implied vol held constant,
no time decay inside the 1-day horizon.
"""
from __future__ import annotations

import math

import numpy as np

SQRT2 = math.sqrt(2.0)


def norm_cdf(x):
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + _erf(x / SQRT2))


_erf = np.vectorize(math.erf, otypes=[float])


def black_price(spot, strike: float, vol: float, expiry: float, kind: str):
    """Black price at zero rates for a European option on one unit of the underlying."""
    if kind not in ("call", "put"):
        raise ValueError("option kind must be 'call' or 'put'")
    if strike <= 0 or vol <= 0 or expiry <= 0:
        raise ValueError("strike, vol and expiry must be positive")
    s = np.asarray(spot, dtype=float)
    sd = vol * math.sqrt(expiry)
    d1 = (np.log(s / strike) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    if kind == "call":
        return s * norm_cdf(d1) - strike * norm_cdf(d2)
    return strike * norm_cdf(-d2) - s * norm_cdf(-d1)


def black_delta(spot: float, strike: float, vol: float, expiry: float, kind: str) -> float:
    sd = vol * math.sqrt(expiry)
    d1 = (math.log(spot / strike) + 0.5 * sd * sd) / sd
    nd1 = float(norm_cdf(d1))
    return nd1 if kind == "call" else nd1 - 1.0


def validate_position(p: dict, factors) -> dict:
    """Return a clean copy of a position dict, or raise ValueError with a readable message."""
    if p.get("factor") not in factors:
        raise ValueError(f"unknown risk factor {p.get('factor')!r}")
    t = p.get("type")
    q = dict(p)
    if t == "linear":
        n = float(p["notional"])
        if not math.isfinite(n) or n == 0 or abs(n) > 1e9:
            raise ValueError("linear notional must be non-zero and at most 1bn USD in size")
        q["notional"] = n
    elif t == "option":
        if p.get("option") not in ("call", "put"):
            raise ValueError("option must be 'call' or 'put'")
        qty, k, v, e = (float(p[x]) for x in ("quantity", "strike_pct", "vol", "expiry_years"))
        if not math.isfinite(qty) or qty == 0 or abs(qty) > 1e12:
            raise ValueError("option quantity must be non-zero")
        if not 0.2 <= k <= 5.0:
            raise ValueError("strike_pct must be between 0.2 and 5.0 (20% to 500% of spot)")
        if not 0.01 <= v <= 3.0:
            raise ValueError("vol must be between 0.01 and 3.0")
        if not 1 / 365 <= e <= 5.0:
            raise ValueError("expiry_years must be between 1 day and 5 years")
        q.update(quantity=qty, strike_pct=k, vol=v, expiry_years=e)
    else:
        raise ValueError("position type must be 'linear' or 'option'")
    return q


def scenario_pnl(positions: list[dict], factors, spot: np.ndarray, scenario_returns: np.ndarray) -> np.ndarray:
    """P&L of each position under each scenario. Returns shape (n_scenarios, n_positions).

    scenario_returns has shape (n_scenarios, n_factors); scenario s moves factor f to spot[f] * (1 + r[s, f]).
    """
    factors = tuple(factors)
    out = np.zeros((scenario_returns.shape[0], len(positions)))
    for j, p in enumerate(positions):
        f = factors.index(p["factor"])
        r = scenario_returns[:, f]
        if p["type"] == "linear":
            out[:, j] = p["notional"] * r
        else:
            s0 = float(spot[f])
            k = p["strike_pct"] * s0
            v0 = black_price(s0, k, p["vol"], p["expiry_years"], p["option"])
            out[:, j] = p["quantity"] * (black_price(s0 * (1.0 + r), k, p["vol"], p["expiry_years"], p["option"]) - v0)
    return out


def exposure_usd(p: dict, factors, spot: np.ndarray) -> float:
    """Dollar delta: USD P&L per 100% move in the factor (so 1% move = exposure / 100)."""
    s0 = float(spot[tuple(factors).index(p["factor"])])
    if p["type"] == "linear":
        return p["notional"]
    d = black_delta(s0, p["strike_pct"] * s0, p["vol"], p["expiry_years"], p["option"])
    return p["quantity"] * d * s0


def market_value(p: dict, factors, spot: np.ndarray) -> float:
    """Option premium value in USD (0 for linear positions, which are marked at par)."""
    if p["type"] == "linear":
        return 0.0
    s0 = float(spot[tuple(factors).index(p["factor"])])
    return float(p["quantity"] * black_price(s0, p["strike_pct"] * s0, p["vol"], p["expiry_years"], p["option"]))
