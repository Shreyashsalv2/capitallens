"""Run the full market-risk and capital analysis for a book, and what-if analysis for new trades."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from .backtest import backtest
from .capital import ima_capital
from .data import FACTOR_LABELS, MarketData
from .explain import explain_book, explain_what_if, usd
from .instruments import exposure_usd, market_value, scenario_pnl, validate_position
from .risk import contributions, es_hs, find_stress_window, rolling_var, scale, var_hs

MAX_NEW_TRADES = 5


@dataclass(frozen=True)
class Config:
    var_conf: float = 0.99
    es_conf: float = 0.975
    window: int = 250  # scenarios per VaR / ES calculation (about one year)
    backtest_days: int = 250
    avg_days: int = 60  # averaging window in the capital formula
    horizon_days: int = 10


DEFAULT_CONFIG = Config()


def describe(p: dict) -> str:
    if p.get("desc"):
        return p["desc"]
    label = FACTOR_LABELS.get(p["factor"], p["factor"]).split(" (")[0]
    if p["type"] == "linear":
        side = "long" if p["notional"] > 0 else "short"
        return f"{side} {label} {usd(abs(p['notional']))}"
    side = "long" if p["quantity"] > 0 else "short"
    return f"{side} {label} {p['option']} ({p['strike_pct'] * 100:.0f}% strike, {p['expiry_years']:g}y)"


def _prepare(positions: list[dict], md: MarketData) -> list[dict]:
    if not positions:
        raise ValueError("the book has no positions")
    out = []
    for i, p in enumerate(positions):
        q = validate_position(p, md.factors)
        q.setdefault("id", f"p{i + 1}")
        q["desc"] = describe(q)
        out.append(q)
    return out


def analyse(positions: list[dict], md: MarketData, cfg: Config = DEFAULT_CONFIG, stress_start: int | None = None) -> dict:
    positions = _prepare(positions, md)
    w = cfg.window
    rets = md.returns()
    rdates = md.return_dates
    need = w + max(cfg.backtest_days, cfg.avg_days)
    if len(rets) < need:
        raise ValueError(f"need at least {need} days of returns, have {len(rets)}")
    pnl = scenario_pnl(positions, md.factors, md.spot, rets)
    total = pnl.sum(axis=1)

    cur = pnl[-w:]
    var1 = var_hs(total[-w:], cfg.var_conf)
    es1 = es_hs(total[-w:], cfg.es_conf)
    if stress_start is None:
        stress_start, _ = find_stress_window(total, w, cfg.var_conf)
    if not 0 <= stress_start <= len(total) - w:
        raise ValueError("stress window is outside the data")
    stress_pnl = total[stress_start:stress_start + w]
    svar1 = var_hs(stress_pnl, cfg.var_conf)

    sq = math.sqrt(cfg.horizon_days)
    var_hist = rolling_var(total[-(w + cfg.avg_days - 1):], w, cfg.var_conf) * sq
    # The book is static, so its stressed VaR is the same on each of the 60 days.
    svar_hist = np.full(cfg.avg_days, svar1 * sq)
    bt = backtest(total, w, cfg.backtest_days, cfg.var_conf)
    cap = ima_capital(var_hist, svar_hist, bt["multiplier"])

    contrib = contributions(cur, cfg.var_conf, cfg.es_conf)
    s_contrib = contributions(pnl[stress_start:stress_start + w], cfg.var_conf, cfg.es_conf)
    pos_out = []
    for j, p in enumerate(positions):
        pos_out.append({
            **{k: p[k] for k in p},
            "factor_label": FACTOR_LABELS.get(p["factor"], p["factor"]),
            "exposure_usd": exposure_usd(p, md.factors, md.spot),
            "market_value": market_value(p, md.factors, md.spot),
            "standalone_var_1d": var_hs(cur[:, j], cfg.var_conf),
            "var_contribution": contrib["var"][j],
            "es_contribution": contrib["es"][j],
            "svar_contribution": s_contrib["var"][j],
        })

    report = {
        "as_of": md.as_of,
        "config": asdict(cfg),
        "spot": {f: float(v) for f, v in zip(md.factors, md.spot, strict=True)},
        "factors": [{"code": f, "label": FACTOR_LABELS.get(f, f)} for f in md.factors],
        "data": {"first_date": md.dates[0], "last_date": md.dates[-1], "days": len(md.dates)},
        "positions": pos_out,
        "metrics": {
            "var_1d": var1, "var_10d": scale(var1, cfg.horizon_days),
            "es_1d": es1, "es_10d": scale(es1, cfg.horizon_days),
            "svar_1d": svar1, "svar_10d": scale(svar1, cfg.horizon_days),
            "var_scenario_date": rdates[-w:][contrib["var_scenario"]],
        },
        "stress": {"start_index": int(stress_start), "start": rdates[stress_start], "end": rdates[stress_start + w - 1]},
        "backtest": {
            "dates": list(rdates[-cfg.backtest_days:]),
            "pnl": bt["pnl"].tolist(),
            "var_forecast": bt["var_forecast"].tolist(),
            "hits": bt["hits"].tolist(),
            "exceptions": bt["exceptions"],
            "zone": bt["zone"],
            "plus_factor": bt["plus_factor"],
            "multiplier": bt["multiplier"],
            "kupiec": bt["kupiec"],
            "christoffersen": bt["christoffersen"],
        },
        "capital": cap,
        "distribution": {"pnl": total[-w:].tolist(), "dates": list(rdates[-w:])},
    }
    report["explanation"] = explain_book(report)
    return report


def what_if(base_positions: list[dict], new_positions: list[dict], md: MarketData, cfg: Config = DEFAULT_CONFIG,
            before: dict | None = None) -> dict:
    """Add new trades to the book and report how VaR, ES and capital change, with a plain-English explanation.

    The stress period stays the one chosen for the current book (a bank's approved stress period
    doesn't move with each trade).
    """
    if not new_positions:
        raise ValueError("add at least one trade")
    if len(new_positions) > MAX_NEW_TRADES:
        raise ValueError(f"at most {MAX_NEW_TRADES} new trades at a time")
    before = before or analyse(base_positions, md, cfg)
    base = _prepare(base_positions, md)
    new = [dict(p, id=f"new{i + 1}") for i, p in enumerate(new_positions)]
    new = [dict(p, desc=describe(validate_position(p, md.factors))) for p in new]
    after = analyse(base + new, md, cfg, stress_start=before["stress"]["start_index"])

    w = cfg.window
    rets = md.returns()[-w:]
    new_clean = [validate_position(p, md.factors) for p in new]
    new_pnl = scenario_pnl(new_clean, md.factors, md.spot, rets).sum(axis=1)
    base_pnl = scenario_pnl(base, md.factors, md.spot, rets).sum(axis=1)
    rho = float(np.corrcoef(new_pnl, base_pnl)[0, 1]) if np.std(new_pnl) > 0 and np.std(base_pnl) > 0 else 0.0
    new_ids = {p["id"] for p in new}
    new_es = sum(p["es_contribution"] for p in after["positions"] if p["id"] in new_ids)

    result = {
        "before": before,
        "after": after,
        "new_positions": [p for p in after["positions"] if p["id"] in new_ids],
        "new_es_contribution": new_es,
        "correlation_with_book": rho,
        "delta": {
            "var_1d": after["metrics"]["var_1d"] - before["metrics"]["var_1d"],
            "es_1d": after["metrics"]["es_1d"] - before["metrics"]["es_1d"],
            "svar_10d": after["metrics"]["svar_10d"] - before["metrics"]["svar_10d"],
            "capital": after["capital"]["total"] - before["capital"]["total"],
            "rwa": after["capital"]["rwa"] - before["capital"]["rwa"],
            "exceptions": after["backtest"]["exceptions"] - before["backtest"]["exceptions"],
        },
    }
    result["explanation"] = explain_what_if(result)
    return result
