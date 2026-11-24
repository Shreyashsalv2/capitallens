"""Basel 2.5 internal-models (IMA) market-risk capital, the structure used under APRA APS 116.

  capital = max(VaR_last,  m * mean(VaR over 60 days))
          + max(sVaR_last, m * mean(sVaR over 60 days))
  m       = 3 + back-testing plus factor (same multiplier for VaR and stressed VaR)
  RWA     = 12.5 * capital
All VaR inputs are 10-day, 99%.
"""
from __future__ import annotations

import numpy as np

RWA_FACTOR = 12.5


def ima_capital(var10_history, svar10_history, multiplier: float) -> dict:
    var10_history = np.asarray(var10_history, dtype=float)
    svar10_history = np.asarray(svar10_history, dtype=float)
    if len(var10_history) == 0 or len(svar10_history) == 0:
        raise ValueError("need at least one day of VaR and stressed VaR")
    if multiplier < 3.0:
        raise ValueError("the regulatory multiplier is at least 3")
    var_last, var_avg = float(var10_history[-1]), float(var10_history.mean())
    svar_last, svar_avg = float(svar10_history[-1]), float(svar10_history.mean())
    var_term = max(var_last, multiplier * var_avg)
    svar_term = max(svar_last, multiplier * svar_avg)
    total = var_term + svar_term
    return {
        "multiplier": multiplier,
        "var_last": var_last,
        "var_avg": var_avg,
        "var_term": var_term,
        "var_binding": "average" if multiplier * var_avg >= var_last else "latest",
        "svar_last": svar_last,
        "svar_avg": svar_avg,
        "svar_term": svar_term,
        "svar_binding": "average" if multiplier * svar_avg >= svar_last else "latest",
        "total": total,
        "rwa": RWA_FACTOR * total,
    }
