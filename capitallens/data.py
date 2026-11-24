"""Load the daily market data and the sample trading book."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MARKET_DATA = os.path.join(DATA_DIR, "market_data.csv")
BOOK = os.path.join(DATA_DIR, "book.json")

FACTOR_LABELS = {
    "EUR": "EUR/USD",
    "GBP": "GBP/USD",
    "AUD": "AUD/USD",
    "JPY": "JPY (USD per yen)",
    "INR": "INR (USD per rupee)",
    "CAD": "CAD (USD per dollar)",
    "BRENT": "Brent crude (USD/bbl)",
    "HENRYHUB": "Henry Hub gas (USD/MMBtu)",
}


@dataclass(frozen=True)
class MarketData:
    """Daily prices: row t is the market on dates[t]; column f is factors[f] in USD per unit."""

    dates: tuple[str, ...]
    factors: tuple[str, ...]
    prices: np.ndarray

    def __post_init__(self):
        if self.prices.shape != (len(self.dates), len(self.factors)):
            raise ValueError("prices shape does not match dates x factors")
        if not np.all(np.isfinite(self.prices)) or np.any(self.prices <= 0):
            raise ValueError("prices must be finite and positive")
        if list(self.dates) != sorted(self.dates) or len(set(self.dates)) != len(self.dates):
            raise ValueError("dates must be unique and ascending")

    @property
    def as_of(self) -> str:
        return self.dates[-1]

    @property
    def spot(self) -> np.ndarray:
        return self.prices[-1]

    def returns(self) -> np.ndarray:
        """Relative 1-day returns between consecutive snapshots, shape (T-1, F). Row i is the move into dates[i+1]."""
        return self.prices[1:] / self.prices[:-1] - 1.0

    @property
    def return_dates(self) -> tuple[str, ...]:
        return self.dates[1:]

    def index(self, factor: str) -> int:
        try:
            return self.factors.index(factor)
        except ValueError:
            raise ValueError(f"unknown risk factor {factor!r}; choose one of {', '.join(self.factors)}") from None


def load_market_data(path: str = MARKET_DATA) -> MarketData:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    if header[0] != "date":
        raise ValueError("first column must be 'date'")
    dates = tuple(r[0] for r in body)
    prices = np.array([[float(x) for x in r[1:]] for r in body], dtype=float)
    return MarketData(dates=dates, factors=tuple(header[1:]), prices=prices)


def load_book(path: str = BOOK) -> list[dict]:
    with open(path) as f:
        return json.load(f)["positions"]
