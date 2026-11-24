import numpy as np
import pytest

from capitallens.instruments import black_delta, black_price, exposure_usd, scenario_pnl, validate_position

FACTORS = ("AAA", "BBB")
SPOT = np.array([100.0, 50.0])


def test_black_atm_call_known_value():
    # Zero rates, ATM: C = S * (2 N(vol*sqrt(T)/2) - 1)
    assert float(black_price(100.0, 100.0, 0.2, 1.0, "call")) == pytest.approx(7.965567, rel=1e-6)


def test_put_call_parity_at_zero_rates():
    for k in (80.0, 100.0, 130.0):
        c = float(black_price(100.0, k, 0.3, 0.5, "call"))
        p = float(black_price(100.0, k, 0.3, 0.5, "put"))
        assert c - p == pytest.approx(100.0 - k)


def test_delta_bounds():
    assert 0 < black_delta(100, 100, 0.2, 1, "call") < 1
    assert -1 < black_delta(100, 100, 0.2, 1, "put") < 0
    assert black_delta(100, 100, 0.2, 1, "call") - black_delta(100, 100, 0.2, 1, "put") == pytest.approx(1.0)


def test_linear_pnl_is_notional_times_return():
    pos = [validate_position({"type": "linear", "factor": "BBB", "notional": -2e6}, FACTORS)]
    r = np.array([[0.0, 0.01], [0.5, -0.02]])
    assert np.allclose(scenario_pnl(pos, FACTORS, SPOT, r)[:, 0], [-2e4, 4e4])


def test_option_full_revaluation_captures_convexity():
    pos = validate_position({"type": "option", "factor": "AAA", "option": "call", "quantity": 1000,
                             "strike_pct": 1.0, "vol": 0.3, "expiry_years": 0.25}, FACTORS)
    r = np.array([[0.0, 0.0], [0.2, 0.0], [-0.2, 0.0]])
    pnl = scenario_pnl([pos], FACTORS, SPOT, r)[:, 0]
    delta_approx = exposure_usd(pos, FACTORS, SPOT) * 0.2
    assert pnl[0] == pytest.approx(0.0)
    assert pnl[1] > delta_approx  # long gamma: gains more than delta on the way up
    assert pnl[2] > -delta_approx  # ... and loses less on the way down


@pytest.mark.parametrize("bad", [
    {"type": "linear", "factor": "ZZZ", "notional": 1},
    {"type": "linear", "factor": "AAA", "notional": 0},
    {"type": "linear", "factor": "AAA", "notional": 5e9},
    {"type": "swap", "factor": "AAA", "notional": 1},
    {"type": "option", "factor": "AAA", "option": "digital", "quantity": 1, "strike_pct": 1, "vol": 0.2, "expiry_years": 1},
    {"type": "option", "factor": "AAA", "option": "call", "quantity": 1, "strike_pct": 9, "vol": 0.2, "expiry_years": 1},
    {"type": "option", "factor": "AAA", "option": "call", "quantity": 1, "strike_pct": 1, "vol": 0, "expiry_years": 1},
])
def test_invalid_positions_rejected(bad):
    with pytest.raises(ValueError):
        validate_position(bad, FACTORS)
