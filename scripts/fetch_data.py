#!/usr/bin/env python3
"""Download the public daily market data CapitalLens uses and write data/market_data.csv.

Sources (all published by datahub.io on GitHub, which mirrors the official series):
  FX rates  -> US Federal Reserve H.10 / FRED     github.com/datasets/exchange-rates
  Brent     -> US Energy Information Admin. (EIA) github.com/datasets/oil-prices
  Henry Hub -> US Energy Information Admin. (EIA) github.com/datasets/natural-gas

Every column in the output is the USD price of one unit of the risk factor:
  EUR, GBP, AUD, JPY, INR, CAD  = USD per 1 unit of that currency (FRED quotes are inverted)
  BRENT                         = USD per barrel
  HENRYHUB                      = USD per MMBtu
Only dates on which every series has a value are kept, so every row is a real, complete
market snapshot (no forward-filling).

Usage:  python3 scripts/fetch_data.py [--start 2005-01-03]
"""
import argparse
import csv
import io
import os
import urllib.request

BASE = "https://raw.githubusercontent.com/datasets"
FX_URL = f"{BASE}/exchange-rates/main/data/daily.csv"
BRENT_URL = f"{BASE}/oil-prices/main/data/brent-daily.csv"
GAS_URL = f"{BASE}/natural-gas/main/data/daily.csv"

# datahub country name -> column name. The source quotes units of currency per 1 USD.
FX_COUNTRIES = {
    "Euro": "EUR",
    "United Kingdom": "GBP",
    "Australia": "AUD",
    "Japan": "JPY",
    "India": "INR",
    "Canada": "CAD",
}
COLUMNS = ["EUR", "GBP", "AUD", "JPY", "INR", "CAD", "BRENT", "HENRYHUB"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "market_data.csv")


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


def to_float(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2005-01-03", help="first date to keep (YYYY-MM-DD)")
    args = ap.parse_args()

    series = {c: {} for c in COLUMNS}
    for row in fetch(FX_URL):
        col = FX_COUNTRIES.get(row["Country"])
        v = to_float(row["Exchange rate"])
        if col and v:
            series[col][row["Date"]] = 1.0 / v  # currency per USD -> USD per currency
    for row in fetch(BRENT_URL):
        v = to_float(row["Price"])
        if v:
            series["BRENT"][row["Date"]] = v
    for row in fetch(GAS_URL):
        v = to_float(row["Price"])
        if v:
            series["HENRYHUB"][row["Date"]] = v

    dates = sorted(d for d in set.intersection(*(set(s) for s in series.values())) if d >= args.start)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date"] + COLUMNS)
        for d in dates:
            w.writerow([d] + [f"{series[c][d]:.8g}" for c in COLUMNS])
    print(f"wrote {len(dates)} rows, {dates[0]} to {dates[-1]} -> {OUT}")


if __name__ == "__main__":
    main()
