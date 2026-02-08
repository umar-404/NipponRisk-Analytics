# NipponRisk Analytics
"""Monte Carlo Value at Risk using a multivariate-Normal return model.

Fits a mean vector and covariance matrix to the aligned asset returns, draws a
large number of 1-day scenarios from the multivariate Normal, projects each to
the weighted portfolio return, and reports tail quantiles as VaR.

Note: the parametric Normal estimate is a complement to historical simulation.
Real equity returns are fat-tailed; the historical VaR is generally the more
conservative/robust figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import MonteCarloParams
from app.risk.portfolio import TICKERS


DEFAULT_PARAMS = MonteCarloParams()


def estimate_moments(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Mean vector and covariance matrix of the tradable asset returns.

    Parameters
    ----------
    returns : pandas.DataFrame
        Aligned daily returns panel (columns include the tradable tickers),
        with no NaN (callers should pass an aligned, cleaned panel).

    Returns
    -------
    (mu, sigma) where mu is shape (k,) and sigma is shape (k, k), both float.
    """
    arr = returns[[*TICKERS]].to_numpy(dtype=float)
    arr = arr[np.all(np.isfinite(arr), axis=1)]
    if arr.shape[0] < 3:
        raise ValueError("Not enough observations to estimate covariance.")
    mu = arr.mean(axis=0)
    sigma = np.cov(arr, rowvar=False, ddof=1)
    return mu, sigma


def monte_carlo_var(
    returns: pd.DataFrame,
    weights: dict[str, float],
    params: MonteCarloParams = DEFAULT_PARAMS,
) -> dict[float, float]:
    """Monte Carlo VaR for the weighted portfolio at given confidence levels.

    Returns
    -------
    dict mapping each confidence level to VaR as a **positive** decimal loss
    (e.g. ``{0.95: 0.024, 0.99: 0.043}``).
    """
    # Weight vector in TICKERS order.
    from app.risk.portfolio import weights_vector

    w = weights_vector(weights)
    mu, sigma = estimate_moments(returns)

    rng = np.random.default_rng(params.random_seed)
    draws = rng.multivariate_normal(mu, sigma, size=params.n_scenarios)
    portfolio_scenarios = draws @ w
    portfolio_scenarios = portfolio_scenarios[np.isfinite(portfolio_scenarios)]

    out: dict[float, float] = {}
    for cl in params.confidence_levels:
        q = np.percentile(portfolio_scenarios, (1.0 - cl) * 100.0)
        out[float(cl)] = float(-q)  # positive loss figure
    return out