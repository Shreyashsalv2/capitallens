"""CapitalLens HTTP API (FastAPI). Deployed as a Vercel Python function; run locally with
`uvicorn api.index:app --reload` from the repo root."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capitallens import __version__  # noqa: E402
from capitallens.data import load_book, load_market_data  # noqa: E402
from capitallens.engine import MAX_NEW_TRADES, analyse, what_if  # noqa: E402

Factor = Literal["EUR", "GBP", "AUD", "JPY", "INR", "CAD", "BRENT", "HENRYHUB"]


class LinearTrade(BaseModel):
    type: Literal["linear"]
    factor: Factor
    notional: float = Field(..., description="USD exposure; positive = long the factor", ge=-1e9, le=1e9)


class OptionTrade(BaseModel):
    type: Literal["option"]
    factor: Factor
    option: Literal["call", "put"]
    quantity: float = Field(..., description="units of the underlying; negative = sold", ge=-1e12, le=1e12)
    strike_pct: float = Field(..., ge=0.2, le=5.0, description="strike as a fraction of spot")
    vol: float = Field(..., ge=0.01, le=3.0, description="implied volatility, e.g. 0.35")
    expiry_years: float = Field(..., ge=1 / 365, le=5.0)


Trade = Annotated[LinearTrade | OptionTrade, Field(discriminator="type")]


class WhatIfRequest(BaseModel):
    trades: list[Trade] = Field(..., min_length=1, max_length=MAX_NEW_TRADES)


app = FastAPI(title="CapitalLens API", version=__version__,
              description="Market-risk VaR, ES, back-testing and Basel 2.5 capital for an FX and energy book.",
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


@lru_cache(maxsize=1)
def _market():
    return load_market_data()


@lru_cache(maxsize=1)
def _book():
    return load_book()


@lru_cache(maxsize=1)
def _summary():
    return analyse(_book(), _market())


@app.get("/api/health")
def health():
    md = _market()
    return {"status": "ok", "version": __version__, "as_of": md.as_of, "days": len(md.dates)}


@app.get("/api/summary")
def summary():
    return _summary()


@app.post("/api/what-if")
def run_what_if(req: WhatIfRequest):
    trades = [t.model_dump() for t in req.trades]
    try:
        res = what_if(_book(), trades, _market(), before=_summary())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    # The full "before" report is already served by /api/summary; return only what the page needs.
    keep = ("metrics", "capital", "backtest", "positions", "stress")
    slim = lambda r: {k: r[k] for k in keep}  # noqa: E731
    return JSONResponse({
        "before": slim(res["before"]),
        "after": slim(res["after"]),
        "new_positions": res["new_positions"],
        "delta": res["delta"],
        "correlation_with_book": res["correlation_with_book"],
        "new_es_contribution": res["new_es_contribution"],
        "explanation": res["explanation"],
    })
