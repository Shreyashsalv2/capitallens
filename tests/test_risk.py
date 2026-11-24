import math

import numpy as np
import pytest

from capitallens.risk import contributions, es_hs, es_weights, find_stress_window, rolling_var, scale, var_hs, var_index


def test_var_index_order_statistics():
    assert var_index(250, 0.99) == 2  # 3rd worst day
    assert var_index(500, 0.99) == 4  # 5th worst
    assert var_index(100, 0.99) == 0  # worst
    assert var_index(10, 0.99) == 0


def test_var_is_third_worst_of_250():
    pnl = np.arange(250, dtype=float) - 100  # worst three: -100, -99, -98
    rng = np.random.default_rng(0)
    rng.shuffle(pnl)
    assert var_hs(pnl, 0.99) == 98.0


def test_es_975_uses_fractional_seventh_observation():
    pnl = -np.arange(1, 251, dtype=float)  # losses 1..250
    worst = np.arange(250, 243, -1, dtype=float)  # 250..244
    expected = (worst[:6].sum() + 0.25 * worst[6]) / 6.25
    assert es_hs(pnl, 0.975) == pytest.approx(expected)


def test_es_weights_sum_to_one():
    for n, c in [(250, 0.975), (250, 0.99), (500, 0.975), (37, 0.9)]:
        assert es_weights(n, c).sum() == pytest.approx(1.0)


def test_es_is_at_least_var_at_same_confidence():
    rng = np.random.default_rng(1)
    for _ in range(20):
        pnl = rng.standard_t(4, 250)
        assert es_hs(pnl, 0.99) >= var_hs(pnl, 0.99) - 1e-12


def test_ten_day_scaling():
    assert scale(1.0, 10) == pytest.approx(math.sqrt(10))


def test_bad_confidence_rejected():
    with pytest.raises(ValueError):
        var_hs([1, 2, 3], 1.5)


def test_contributions_add_up_to_book_totals():
    rng = np.random.default_rng(2)
    m = rng.normal(size=(250, 5)) * [1, 2, 3, 0.5, 4]
    c = contributions(m, 0.99, 0.975)
    total = m.sum(axis=1)
    assert sum(c["var"]) == pytest.approx(var_hs(total, 0.99))
    assert sum(c["es"]) == pytest.approx(es_hs(total, 0.975))


def test_hedge_has_negative_contribution():
    rng = np.random.default_rng(3)
    x = rng.normal(size=250)
    m = np.column_stack([10 * x, -3 * x + 0.1 * rng.normal(size=250)])
    c = contributions(m)
    assert c["es"][0] > 0 > c["es"][1]


def test_rolling_var_matches_brute_force():
    rng = np.random.default_rng(4)
    pnl = rng.normal(size=400)
    fast = rolling_var(pnl, 250, 0.99)
    slow = [var_hs(pnl[i:i + 250], 0.99) for i in range(151)]
    assert np.allclose(fast, slow)


def test_stress_window_finds_planted_crash():
    rng = np.random.default_rng(5)
    pnl = rng.normal(size=1000)
    pnl[600:610] = -50
    start, v = find_stress_window(pnl, 250, 0.99)
    crash_days_inside = len(set(range(start, start + 250)) & set(range(600, 610)))
    assert crash_days_inside >= 3  # VaR is the 3rd-worst day, so 3 crash days are enough
    assert v == 50
