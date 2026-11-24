"""VaR back-testing: exceptions, the Basel traffic light, and the Kupiec and Christoffersen tests."""
from __future__ import annotations

import math

import numpy as np

from .risk import rolling_var

# Basel Committee (1996) traffic-light table for 250 daily observations at 99% VaR:
# number of exceptions -> (zone, plus factor added to the multiplier of 3).
TRAFFIC_LIGHT = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85}
BASE_MULTIPLIER = 3.0


def traffic_light(exceptions: int, observations: int = 250) -> dict:
    if observations != 250:
        raise ValueError("the Basel traffic light is defined for 250 observations")
    if exceptions < 0:
        raise ValueError("exceptions cannot be negative")
    if exceptions <= 4:
        zone = "green"
    elif exceptions <= 9:
        zone = "amber"
    else:
        zone = "red"
    plus = TRAFFIC_LIGHT.get(exceptions, 1.0)
    return {"zone": zone, "plus_factor": plus, "multiplier": BASE_MULTIPLIER + plus}


def chi2_sf_1dof(x: float) -> float:
    """P(X >= x) for a chi-square variable with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def _xlogy(x: float, y: float) -> float:
    return 0.0 if x == 0 else x * math.log(y)


def kupiec_pof(exceptions: int, observations: int, p: float = 0.01) -> dict:
    """Kupiec (1995) proportion-of-failures likelihood-ratio test. H0: exception rate = p."""
    x, n = exceptions, observations
    if not 0 <= x <= n or n == 0:
        raise ValueError("need 0 <= exceptions <= observations and observations > 0")
    phat = x / n
    ll0 = _xlogy(n - x, 1 - p) + _xlogy(x, p)
    ll1 = _xlogy(n - x, 1 - phat) + _xlogy(x, phat)
    lr = max(0.0, -2.0 * (ll0 - ll1))
    return {"lr": lr, "p_value": chi2_sf_1dof(lr), "expected": n * p}


def christoffersen_independence(hits) -> dict:
    """Christoffersen (1998) test that exceptions do not cluster. H0: today's exception doesn't depend on yesterday's."""
    h = np.asarray(hits, dtype=bool).astype(int)
    if len(h) < 2:
        raise ValueError("need at least two observations")
    prev, cur = h[:-1], h[1:]
    n00 = int(np.sum((prev == 0) & (cur == 0)))
    n01 = int(np.sum((prev == 0) & (cur == 1)))
    n10 = int(np.sum((prev == 1) & (cur == 0)))
    n11 = int(np.sum((prev == 1) & (cur == 1)))
    pi0 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    ll_null = _xlogy(n00 + n10, 1 - pi) + _xlogy(n01 + n11, pi)
    ll_alt = _xlogy(n00, 1 - pi0) + _xlogy(n01, pi0) + _xlogy(n10, 1 - pi1) + _xlogy(n11, pi1)
    lr = max(0.0, -2.0 * (ll_null - ll_alt))
    return {"lr": lr, "p_value": chi2_sf_1dof(lr), "n00": n00, "n01": n01, "n10": n10, "n11": n11}


def backtest(total_pnl: np.ndarray, window: int = 250, days: int = 250, conf: float = 0.99) -> dict:
    """Back-test the last `days` days: the VaR forecast for day t uses only the `window` days before t."""
    total_pnl = np.asarray(total_pnl, dtype=float)
    if len(total_pnl) < window + days:
        raise ValueError(f"need {window + days} days of P&L to back-test, have {len(total_pnl)}")
    forecasts = rolling_var(total_pnl[-(window + days):-1], window, conf)
    actual = total_pnl[-days:]
    hits = actual < -forecasts
    x = int(hits.sum())
    tl = traffic_light(x, days) if days == 250 else {"zone": None, "plus_factor": None, "multiplier": None}
    return {
        "var_forecast": forecasts,
        "pnl": actual,
        "hits": hits,
        "exceptions": x,
        **tl,
        "kupiec": kupiec_pof(x, days, 1 - conf),
        "christoffersen": christoffersen_independence(hits),
    }
