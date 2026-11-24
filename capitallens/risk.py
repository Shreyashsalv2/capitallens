"""Historical-simulation risk measures.

Conventions (losses are positive numbers):
  VaR(c)  = minus the k-th worst P&L, k = ceil(n * (1 - c)). With n = 250 and c = 99% that is the 3rd worst day.
  ES(c)   = minus the average of the worst n * (1 - c) outcomes, with the last one weighted fractionally
            (n = 250, c = 97.5% -> worst 6 days plus a quarter of the 7th, divided by 6.25).
  10-day  = 1-day * sqrt(10) (square-root-of-time scaling, as Basel 2.5 allows).
"""
from __future__ import annotations

import math

import numpy as np


def _tail_count(n: int, conf: float) -> float:
    if not 0.5 < conf < 1.0:
        raise ValueError("confidence must be between 0.5 and 1")
    if n < 1:
        raise ValueError("need at least one scenario")
    return n * (1.0 - conf)


def var_index(n: int, conf: float) -> int:
    """0-based position, in ascending sorted P&L, of the scenario that sets VaR."""
    return max(1, math.ceil(round(_tail_count(n, conf), 9))) - 1


def var_hs(pnl, conf: float = 0.99) -> float:
    x = np.sort(np.asarray(pnl, dtype=float))
    return float(-x[var_index(len(x), conf)])


def es_weights(n: int, conf: float) -> np.ndarray:
    """Weights over ascending sorted P&L that average the worst n*(1-conf) outcomes."""
    m = _tail_count(n, conf)
    k = int(math.floor(round(m, 9)))
    w = np.zeros(n)
    w[:k] = 1.0
    if k < n and m - k > 1e-12:
        w[k] = m - k
    return w / m


def es_hs(pnl, conf: float = 0.975) -> float:
    x = np.sort(np.asarray(pnl, dtype=float))
    return float(-(es_weights(len(x), conf) @ x))


def scale(value: float, days: int = 10) -> float:
    return float(value * math.sqrt(days))


def contributions(pnl_matrix: np.ndarray, var_conf: float = 0.99, es_conf: float = 0.975) -> dict:
    """Split the book's VaR and ES by position. Both splits add up exactly to the book total.

    VaR contribution = minus each position's P&L in the scenario that sets the book's VaR.
    ES contribution  = minus each position's weighted average P&L over the book's tail scenarios.
    """
    total = pnl_matrix.sum(axis=1)
    order = np.argsort(total, kind="stable")
    n = len(total)
    var_scn = order[var_index(n, var_conf)]
    w = es_weights(n, es_conf)
    es_c = -(w @ pnl_matrix[order])
    return {"var": (-pnl_matrix[var_scn]).tolist(), "es": es_c.tolist(), "var_scenario": int(var_scn)}


def rolling_var(total_pnl: np.ndarray, window: int, conf: float) -> np.ndarray:
    """VaR from every trailing window: out[i] uses total_pnl[i : i + window]."""
    total_pnl = np.asarray(total_pnl, dtype=float)
    if len(total_pnl) < window:
        raise ValueError(f"need at least {window} scenarios, have {len(total_pnl)}")
    views = np.lib.stride_tricks.sliding_window_view(total_pnl, window)
    k = var_index(window, conf)
    return -np.partition(views, k, axis=1)[:, k]


def find_stress_window(total_pnl: np.ndarray, window: int = 250, conf: float = 0.99) -> tuple[int, float]:
    """Start index of the trailing window with the highest VaR for this book, and that VaR."""
    v = rolling_var(total_pnl, window, conf)
    i = int(np.argmax(v))
    return i, float(v[i])
