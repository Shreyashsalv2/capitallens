import math

import numpy as np
import pytest

from capitallens.backtest import backtest, chi2_sf_1dof, christoffersen_independence, kupiec_pof, traffic_light
from capitallens.risk import var_hs


@pytest.mark.parametrize("x,zone,mult", [
    (0, "green", 3.0), (4, "green", 3.0), (5, "amber", 3.4), (6, "amber", 3.5), (7, "amber", 3.65),
    (8, "amber", 3.75), (9, "amber", 3.85), (10, "red", 4.0), (25, "red", 4.0),
])
def test_basel_traffic_light(x, zone, mult):
    t = traffic_light(x)
    assert t["zone"] == zone
    assert t["multiplier"] == pytest.approx(mult)


def test_traffic_light_needs_250_days():
    with pytest.raises(ValueError):
        traffic_light(3, 100)


def test_chi2_critical_value():
    assert chi2_sf_1dof(3.841458820694124) == pytest.approx(0.05, abs=1e-9)
    assert chi2_sf_1dof(0) == 1.0


def test_kupiec_zero_exceptions():
    k = kupiec_pof(0, 250, 0.01)
    assert k["lr"] == pytest.approx(-2 * 250 * math.log(0.99))
    assert k["p_value"] == pytest.approx(0.02497, abs=1e-4)


def test_kupiec_matches_formula():
    x, n, p = 10, 250, 0.01
    phat = x / n
    lr = -2 * ((n - x) * math.log(1 - p) + x * math.log(p) - (n - x) * math.log(1 - phat) - x * math.log(phat))
    assert kupiec_pof(x, n, p)["lr"] == pytest.approx(lr)
    assert kupiec_pof(x, n, p)["p_value"] < 0.01  # 10 exceptions rejects 99% coverage


def test_kupiec_accepts_expected_rate():
    assert kupiec_pof(2, 250, 0.01)["p_value"] > 0.5


def test_christoffersen_detects_clustering():
    clustered = np.zeros(250, dtype=bool)
    clustered[100:106] = True
    spread = np.zeros(250, dtype=bool)
    spread[[20, 60, 100, 140, 180, 220]] = True
    assert christoffersen_independence(clustered)["p_value"] < 0.01
    assert christoffersen_independence(spread)["p_value"] > 0.3


def test_backtest_uses_only_past_data():
    rng = np.random.default_rng(9)
    pnl = rng.normal(size=700)
    bt = backtest(pnl, window=250, days=250)
    for i in [0, 1, 137, 249]:
        t = len(pnl) - 250 + i
        assert bt["var_forecast"][i] == pytest.approx(var_hs(pnl[t - 250:t]))
    manual = sum(pnl[len(pnl) - 250 + i] < -bt["var_forecast"][i] for i in range(250))
    assert bt["exceptions"] == manual


def test_backtest_flags_a_planted_loss():
    pnl = np.random.default_rng(10).normal(size=600)
    pnl[-5] = -100
    bt = backtest(pnl)
    assert bt["hits"][-5]


def test_backtest_needs_enough_history():
    with pytest.raises(ValueError):
        backtest(np.zeros(300))
