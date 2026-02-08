# NipponRisk Analytics
"""Historical Value at Risk (Historical Simulation) for the portfolio.

VaR is reported as a **positive daily loss** figure. A 95% VaR of 0.023 means
there is a 5% chance the portfolio loses more than 2.3% in a single day
(historical method, 1-day horizon at the given confidence level).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.risk.portfolio import portfolio_returns


def historical_var(
    returns: pd.DataFrame,
    weights: dict[str, float],
    confidence_levels: tuple[float, ...] = (0.95, 0.99),
) -> dict[float, float]:
    """Compute historical-simulation VaR for the weighted portfolio.

    Parameters
    ----------
    returns : pandas.DataFrame
        Aligned daily returns panel (columns include the tradable tickers).
    weights : dict[str, float]
        Portfolio weights (any scale; normalized internally).
    confidence_levels : tuple[float, ...]
        Confidence levels to report (e.g. 0.95 -> 95%).

    Returns
    -------
    dict mapping each confidence level to its VaR as a **positive** decimal
    loss (e.g. ``{0.95: 0.023, 0.99: 0.041}``).
    """
    pr = portfolio_returns(returns, weights).to_numpy(dtype=float)
    pr = pr[np.isfinite(pr)]
    if pr.size == 0:
        raise ValueError("No finite portfolio returns available to compute VaR.")

    out: dict[float, float] = {}
    for cl in confidence_levels:
        # q is the loss quantile; pr are returns (mostly negative in the tail).
        q = np.percentile(pr, (1.0 - cl) * 100.0)
        out[float(cl)] = float(-q)  # positive loss figure
    return out