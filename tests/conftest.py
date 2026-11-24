import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capitallens.data import MarketData  # noqa: E402


@pytest.fixture
def synthetic_market():
    """700 days of seeded two-factor prices with a planted crash between days 300 and 330."""
    rng = np.random.default_rng(7)
    n = 700
    r = rng.normal(0, 0.01, size=(n - 1, 2))
    r[300:330] *= 6  # stress period
    prices = 100 * np.vstack([np.ones(2), np.cumprod(1 + r, axis=0)])
    dates = tuple(f"D{i:04d}" for i in range(n))
    return MarketData(dates=dates, factors=("AAA", "BBB"), prices=prices)
