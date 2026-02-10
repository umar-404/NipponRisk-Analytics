# NipponRisk Analytics
"""Analysis orchestration: data -> risk engine -> JSON-safe response payload.

This is the heart of ``POST /api/analyze``. It loads the aligned returns panel,
normalizes the requested weights, computes every metric, and returns a plain
data structure (no numpy/pandas types) that the router/Pydantic serialize to
JSON cleanly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import BENCHMARK, TICKERS
from app.data.loader import load_returns_panel
from app.risk.beta import asset_betas, portfolio_beta
from app.risk.drawdown import drawdown_series, max_drawdown
from app.risk.monte_carlo import monte_carlo_var
from app.risk.portfolio import cumulative_equity, normalize_weights, portfolio_returns
from app.risk.stress import stress_test_all
from app.risk.var import historical_var


def _round_dict(d: dict[str, float], nd: int = 6) -> dict[str, float]:
    return {k: round(float(v), nd) for k, v in d.items()}


def run_analysis(weights: dict[str, float], returns: pd.DataFrame | None = None) -> dict:
    """Compute the full analysis for given weights.

    Parameters
    ----------
    weights : dict[str, float]
        Weights per tradable ticker (any scale).
    returns : pandas.DataFrame | None
        Override the cached returns panel (used for tests). Defaults to loading
        the cached aligned panel.

    Returns
    -------
    dict
        A JSON-serializable payload matching ``schemas.AnalysisResult``.
    """
    panel = returns if returns is not None else load_returns_panel()

    # Normalize weights over tradable tickers (drops unknown, clips negatives).
    w_norm = normalize_weights(weights)
    pr = portfolio_returns(panel, w_norm).dropna()
    pr = pr[np.isfinite(pr)]

    # Portfolio-level series (aligned to the panel index).
    idx = pr.index
    bench_returns = panel.loc[idx, BENCHMARK].fillna(0.0)

    equity = cumulative_equity(pr, start=100.0)
    bench_equity = cumulative_equity(bench_returns, start=100.0)

    hvar = historical_var(panel, w_norm, (0.95, 0.99))
    mcvar = monte_carlo_var(panel, w_norm)
    ab = asset_betas(panel)
    pbeta = portfolio_beta(panel, w_norm)
    max_dd = max_drawdown(pr)

    stress = stress_test_all(panel, w_norm)

    return {
        "tickers": list(TICKERS),
        "weights_norm": _round_dict(w_norm),
        "dates": [d.isoformat() for d in idx],
        "portfolio_returns": [round(float(v), 8) for v in pr],
        "benchmark_returns": [round(float(v), 8) for v in bench_returns],
        "equity_curve": [round(float(v), 6) for v in equity],
        "benchmark_equity": [round(float(v), 6) for v in bench_equity],
        "var": {
            "historical": {"p95": round(hvar[0.95], 6), "p99": round(hvar[0.99], 6)},
            "monte_carlo": {"p95": round(mcvar[0.95], 6), "p99": round(mcvar[0.99], 6)},
        },
        "max_drawdown": round(max_dd, 6),
        "asset_betas": _round_dict(ab),
        "portfolio_beta": round(pbeta, 6),
        "stress": stress,
        "data_start": idx.min().isoformat(),
        "data_end": idx.max().isoformat(),
        "n_obs": int(len(idx)),
    }


def health_payload(returns: pd.DataFrame | None = None) -> dict:
    """Small summary for the health endpoint."""
    from app.config import CACHE_MAX_AGE_SECONDS

    panel = returns if returns is not None else load_returns_panel()
    return {
        "status": "ok",
        "n_obs": int(len(panel)),
        "data_start": panel.index.min().isoformat(),
        "data_end": panel.index.max().isoformat(),
        "cache_seconds": int(CACHE_MAX_AGE_SECONDS),
    }