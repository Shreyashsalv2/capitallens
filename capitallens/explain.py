"""Plain-English commentary for people who don't read risk reports every day."""
from __future__ import annotations


def usd(v: float) -> str:
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        s = f"{a / 1e9:.2f}bn"
    elif a >= 1e6:
        s = f"{a / 1e6:.2f}m"
    elif a >= 1e3:
        s = f"{a / 1e3:.0f}k"
    else:
        s = f"{a:.0f}"
    return f"{sign}${s}"


def pct(v: float, digits: int = 0) -> str:
    return f"{v * 100:.{digits}f}%"


def _test_phrase(name: str, p: float, reject: str, accept: str) -> str:
    return f"the {name} test {reject if p < 0.05 else accept} (p = {p:.2f})"


def explain_book(r: dict) -> list[str]:
    m, bt, cap, st = r["metrics"], r["backtest"], r["capital"], r["stress"]
    pos = sorted(r["positions"], key=lambda p: p["es_contribution"], reverse=True)
    top = pos[0]
    hedges = sorted((p for p in pos if p["es_contribution"] < 0), key=lambda p: p["es_contribution"])
    hedges = [h for h in hedges if -h["es_contribution"] >= 0.01 * m["es_1d"]]
    out = [
        f"On a bad day, one that happens about once in 100 trading days, this book loses at least {usd(m['var_1d'])}. "
        f"That is its 1-day 99% VaR ({usd(m['var_10d'])} over 10 days). On the worst 2.5% of days it loses "
        f"{usd(m['es_1d'])} on average (Expected Shortfall).",
        f"Replaying the worst 250-day stretch in the data for this book ({st['start']} to {st['end']}) gives a 10-day "
        f"stressed VaR of {usd(m['svar_10d'])}, {m['svar_10d'] / m['var_10d']:.1f} times today's VaR.",
        f"Back-testing over the last 250 days found {bt['exceptions']} days when the loss was bigger than the VaR forecast "
        f"({bt['kupiec']['expected']:.1f} expected). That puts the model in the {bt['zone']} zone with a capital "
        f"multiplier of {bt['multiplier']:.2f}; "
        + _test_phrase("Kupiec coverage", bt["kupiec"]["p_value"], "rejects 99% coverage", "does not reject 99% coverage")
        + ", and "
        + _test_phrase("Christoffersen", bt["christoffersen"]["p_value"], "finds the exceptions cluster", "finds no clustering")
        + ".",
        f"Market-risk capital is {usd(cap['total'])} ({usd(cap['rwa'])} of risk-weighted assets). The stressed-VaR term "
        f"is {pct(cap['svar_term'] / cap['total'])} of it, so the capital depends more on how the book behaves in a crisis "
        f"than on recent markets." if cap["svar_term"] >= cap["var_term"] else
        f"Market-risk capital is {usd(cap['total'])} ({usd(cap['rwa'])} of risk-weighted assets). The VaR term is "
        f"{pct(cap['var_term'] / cap['total'])} of it, so recent markets drive the capital more than the stress period.",
        f"The biggest risk driver is {top['desc']}, at {pct(top['es_contribution'] / m['es_1d'])} of Expected Shortfall."
        + (f" The biggest hedge is {hedges[0]['desc']}, which offsets {pct(-hedges[0]['es_contribution'] / m['es_1d'])}."
           if hedges else ""),
    ]
    return out


def explain_what_if(w: dict) -> list[str]:
    b, a = w["before"], w["after"]
    d_cap = a["capital"]["total"] - b["capital"]["total"]
    names = ", ".join(t["desc"] for t in w["new_positions"])
    direction = "raises" if d_cap > 0 else "lowers"
    out = [
        f"Adding {names} {direction} market-risk capital by {usd(abs(d_cap))} "
        f"({pct(d_cap / b['capital']['total'], 1)}), from {usd(b['capital']['total'])} to {usd(a['capital']['total'])}. "
        f"Risk-weighted assets move by {usd(a['capital']['rwa'] - b['capital']['rwa'])}.",
        f"1-day 99% VaR goes from {usd(b['metrics']['var_1d'])} to {usd(a['metrics']['var_1d'])}, and Expected Shortfall "
        f"from {usd(b['metrics']['es_1d'])} to {usd(a['metrics']['es_1d'])}.",
    ]
    tail = w["new_es_contribution"]
    rho = w["correlation_with_book"]
    if tail > 0:
        why = (f"On the book's worst days the new trade loses {usd(tail)} on average, so it adds to the losses the book "
               f"already has")
    else:
        why = (f"On the book's worst days the new trade gains {usd(-tail)} on average, so it partly hedges the book")
    out.append(why + f" (its daily P&L has a correlation of {rho:+.2f} with the existing book).")
    d_var_term = a["capital"]["var_term"] - b["capital"]["var_term"]
    d_svar_term = a["capital"]["svar_term"] - b["capital"]["svar_term"]
    if abs(d_cap) > 0:
        bigger = "stressed-VaR" if abs(d_svar_term) >= abs(d_var_term) else "VaR"
        out.append(
            f"Most of the change comes from the {bigger} term: the VaR term moves by {usd(d_var_term)} and the "
            f"stressed-VaR term (stress period {a['stress']['start']} to {a['stress']['end']}) by {usd(d_svar_term)}."
        )
    bx, ax = b["backtest"]["exceptions"], a["backtest"]["exceptions"]
    if ax != bx or a["backtest"]["multiplier"] != b["backtest"]["multiplier"]:
        out.append(
            f"Back-testing exceptions change from {bx} to {ax}, which moves the multiplier from "
            f"{b['backtest']['multiplier']:.2f} to {a['backtest']['multiplier']:.2f} ({a['backtest']['zone']} zone)."
        )
    else:
        out.append(f"Back-testing stays in the {a['backtest']['zone']} zone with {ax} exceptions, so the multiplier "
                   f"stays at {a['backtest']['multiplier']:.2f}.")
    top_b = max(b["positions"], key=lambda p: p["es_contribution"])["desc"]
    top_a = max(a["positions"], key=lambda p: p["es_contribution"])["desc"]
    if top_a != top_b:
        out.append(f"The biggest risk driver changes from {top_b} to {top_a}.")
    return out
