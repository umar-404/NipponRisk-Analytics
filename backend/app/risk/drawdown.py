# NipponRisk Analytics
"""Maximum drawdown and the full drawdown time series.

Drawdown measures peak-to-trough loss: ``dd_t = equity_t / running_peak_t - 1``.
Runner's drawdown series is expressed as a non-positive fraction (0 or less),
and the maximum drawdown is the most negative value in the sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.risk.portfolio import cumulative_equity, portfolio_returns


def drawdown_series(returns: pd.Series, start: float = 100.0) -> pd.Series:
    """Full drawdown time series (<= 0) for a return series or equity curve."""
    equity = cumulative_equity(returns, start)
    running_peak = equity.cummax()
    dd = equity / running_peak - 1.0
    dd = dd.clip(upper=0.0)
    dd.name = "drawdown"
    return dd


def max_drawdown(returns: pd.Series) -> float:
    """Most severe peak-to-trough loss (<= 0) for a return series."""
    dd = drawdown_series(returns)
    if dd.empty:
        raise ValueError("Cannot compute max drawdown on an empty series.")
    return float(dd.min())


def portfolio_max_drawdown(
    returns: pd.DataFrame, weights: dict[str, float], start: float = 100.0
) -> float:
    """Max drawdown of the weighted portfolio across the full sample."""
    pr = portfolio_returns(returns, weights)
    return max_drawdown(pr.dropna())