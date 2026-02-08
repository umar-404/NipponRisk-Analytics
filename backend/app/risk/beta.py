# NipponRisk Analytics
"""Asset-to-benchmark Beta relative to the Nikkei 225 (^N225).

Beta is the slope of the asset's returns regressed on the benchmark returns:
``beta = Cov(r_asset, r_bench) / Var(r_bench)``. The portfolio beta is the
weighted average of the per-asset betas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import BENCHMARK, TICKERS
from app.data.cleaner import assert_benchmark_present
from app.risk.portfolio import weights_vector


def asset_betas(returns: pd.DataFrame) -> dict[str, float]:
    """Per-asset beta for every tradable ticker vs the benchmark.

    Parameters
    ----------
    returns : pandas.DataFrame
        Aligned returns panel containing the benchmark column ``^N225``.
    """
    assert_benchmark_present(returns)
    bench = returns[BENCHMARK].to_numpy(dtype=float)
    bench = bench[np.isfinite(bench)]
    var_bench = bench.var(ddof=1)
    if var_bench <= 0:
        raise ValueError("Benchmark variance is zero — beta is undefined.")

    betas: dict[str, float] = {}
    for ticker in TICKERS:
        assets = returns[ticker].to_numpy(dtype=float)
        mask = np.isfinite(assets) & np.isfinite(bench)
        a, b = assets[mask], bench[mask]
        cov = np.cov(a, b, ddof=1)[0, 1]
        betas[ticker] = float(cov / var_bench)
    return betas


def portfolio_beta(returns: pd.DataFrame, weights: dict[str, float]) -> float:
    """Weighted-average portfolio beta vs the benchmark."""
    ab = asset_betas(returns)
    w = weights_vector(weights)
    return float(np.dot([ab[t] for t in TICKERS], w))