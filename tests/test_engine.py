import json

import numpy as np
import pytest

from capitallens.data import load_book, load_market_data
from capitallens.engine import analyse, what_if
from capitallens.risk import var_hs

BOOK = [
    {"id": "a", "type": "linear", "factor": "AAA", "notional": 1e6},
    {"id": "b", "type": "linear", "factor": "BBB", "notional": -4e5},
]


def test_report_is_consistent(synthetic_market):
    r = analyse(BOOK, synthetic_market)
    m, cap = r["metrics"], r["capital"]
    assert m["var_10d"] == pytest.approx(m["var_1d"] * np.sqrt(10))
    assert m["es_1d"] >= m["var_1d"] * 0.9
    assert sum(p["es_contribution"] for p in r["positions"]) == pytest.approx(m["es_1d"])
    assert sum(p["var_contribution"] for p in r["positions"]) == pytest.approx(m["var_1d"])
    assert cap["total"] == pytest.approx(cap["var_term"] + cap["svar_term"])
    assert cap["multiplier"] == r["backtest"]["multiplier"]
    assert len(r["backtest"]["pnl"]) == 250
    json.dumps(r)  # the API returns it as JSON


def test_stress_window_covers_planted_crash(synthetic_market):
    r = analyse(BOOK, synthetic_market)
    start = r["stress"]["start_index"]
    assert start <= 330 and start + 250 >= 300
    assert r["metrics"]["svar_1d"] > r["metrics"]["var_1d"]


def test_what_if_equals_analysing_the_combined_book(synthetic_market):
    trade = {"type": "linear", "factor": "AAA", "notional": 5e5}
    w = what_if(BOOK, [trade], synthetic_market)
    direct = analyse(BOOK + [trade], synthetic_market, stress_start=w["before"]["stress"]["start_index"])
    assert w["after"]["capital"]["total"] == pytest.approx(direct["capital"]["total"])
    assert w["delta"]["capital"] == pytest.approx(direct["capital"]["total"] - w["before"]["capital"]["total"])
    assert w["after"]["stress"] == w["before"]["stress"]


def test_hedge_lowers_capital_and_says_so(synthetic_market):
    hedge = {"type": "linear", "factor": "AAA", "notional": -9e5}
    w = what_if(BOOK, [hedge], synthetic_market)
    assert w["delta"]["capital"] < 0
    assert w["correlation_with_book"] < 0
    assert "lowers" in w["explanation"][0]
    assert "hedges" in w["explanation"][2]


def test_adding_risk_raises_capital_and_says_so(synthetic_market):
    w = what_if(BOOK, [{"type": "linear", "factor": "AAA", "notional": 2e6}], synthetic_market)
    assert w["delta"]["capital"] > 0
    assert "raises" in w["explanation"][0]


def test_what_if_limits(synthetic_market):
    with pytest.raises(ValueError):
        what_if(BOOK, [], synthetic_market)
    with pytest.raises(ValueError):
        what_if(BOOK, [{"type": "linear", "factor": "AAA", "notional": 1}] * 6, synthetic_market)
    with pytest.raises(ValueError):
        what_if(BOOK, [{"type": "linear", "factor": "NOPE", "notional": 1}], synthetic_market)


def test_real_data_and_sample_book():
    md = load_market_data()
    r = analyse(load_book(), md)
    assert md.factors == ("EUR", "GBP", "AUD", "JPY", "INR", "CAD", "BRENT", "HENRYHUB")
    assert len(md.dates) > 4000 and md.dates[0] >= "2005-01-01"
    assert r["as_of"] == md.dates[-1]
    assert r["metrics"]["var_1d"] == pytest.approx(var_hs(r["distribution"]["pnl"]))
    assert r["backtest"]["zone"] in ("green", "amber", "red")
    assert len(r["explanation"]) == 5
