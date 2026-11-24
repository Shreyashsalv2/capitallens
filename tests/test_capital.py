import pytest

from capitallens.capital import ima_capital


def test_average_term_binds_in_normal_times():
    c = ima_capital([10.0] * 60, [20.0] * 60, 3.0)
    assert c["var_term"] == 30.0 and c["var_binding"] == "average"
    assert c["svar_term"] == 60.0
    assert c["total"] == 90.0
    assert c["rwa"] == pytest.approx(90.0 * 12.5)


def test_latest_term_binds_after_a_spike():
    hist = [10.0] * 59 + [100.0]  # average 11.5, times 3 = 34.5 < 100
    c = ima_capital(hist, [1.0] * 60, 3.0)
    assert c["var_term"] == 100.0 and c["var_binding"] == "latest"


def test_amber_multiplier_raises_capital():
    green = ima_capital([10.0] * 60, [20.0] * 60, 3.0)["total"]
    amber = ima_capital([10.0] * 60, [20.0] * 60, 3.5)["total"]
    assert amber == pytest.approx(green * 3.5 / 3.0)


def test_multiplier_floor():
    with pytest.raises(ValueError):
        ima_capital([1.0], [1.0], 2.5)
