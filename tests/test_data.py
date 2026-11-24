import csv

import numpy as np
import pytest

from capitallens.data import MARKET_DATA, MarketData, load_book


def test_market_data_file_is_complete():
    with open(MARKET_DATA) as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["date", "EUR", "GBP", "AUD", "JPY", "INR", "CAD", "BRENT", "HENRYHUB"]
    dates = [r[0] for r in rows[1:]]
    assert dates == sorted(set(dates))
    for r in rows[1:]:
        assert len(r) == 9 and all(float(x) > 0 for x in r[1:])


def test_fx_is_usd_per_unit():
    from capitallens.data import load_market_data
    md = load_market_data()
    spot = dict(zip(md.factors, md.spot, strict=True))
    assert 0.5 < spot["EUR"] < 2.0  # USD per euro, not euros per USD
    assert spot["JPY"] < 0.05 and spot["INR"] < 0.05


def test_market_data_rejects_bad_input():
    with pytest.raises(ValueError):
        MarketData(("b", "a"), ("X",), np.array([[1.0], [2.0]]))
    with pytest.raises(ValueError):
        MarketData(("a", "b"), ("X",), np.array([[1.0], [-2.0]]))


def test_sample_book_loads():
    book = load_book()
    assert len(book) == 10 and len({p["id"] for p in book}) == 10
