# NipponRisk Analytics
"""Portfolio helpers: weight validation/normalization and portfolio returns.

Weights are supplied per asset (the benchmark `^N225` is never a weightable
position — it is used only as the beta/stress reference).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import TICKERS


def normalize_weights(weights: dict[str, float], default: str = "equal") -> dict[str, float]:
    """Validate & normalize a weight map over the tradable universe.

    - Drops any keys that aren't a known tradable ticker (with a warning).
    - Clips negatives to 0 and renormalizes so weights sum to 1.
    - If the (usable) weights sum to ~0, falls back to equal weight.

    Parameters
    ----------
    weights : dict[str, float]
        Mapping ticker -> weight (any scale; e.g. 25/25/25/25 or 0.25...).
    default : str
        ``"equal"`` gives equal weights when nothing usable is provided.

    Returns
    -------
    dict[str, float]
        Normalized weights summing to 1.0 over ``TICKERS``.
    """
    usable = {t: float(w) for t, w in weights.items() if t in TICKERS}
    unknown = [t for t in weights if t not in TICKERS]
    if unknown:
        print(f"[normalize_weights] ignoring non-tradable/non-ticker keys: {unknown}")

    if not usable:
        usable = {t: 1.0 for t in TICKERS}

    weights_vec = np.clip(np.array([usable.get(t, 0.0) for t in TICKERS]), 0.0, None)
    total = weights_vec.sum()
    if total <= 1e-9:
        weights_vec = np.full(len(TICKERS), 1.0 / len(TICKERS))
    else:
        weights_vec = weights_vec / total

    if default == "equal" and not any(weights):
        weights_vec = np.full(len(TICKERS), 1.0 / len(TICKERS))

    return {t: float(w) for t, w in zip(TICKERS, weights_vec)}


def weights_vector(weights: dict[str, float]) -> np.ndarray:
    """Normalized weight vector aligned with ``config.TICKERS`` order."""
    norm = normalize_weights(weights)
    return np.array([norm[t] for t in TICKERS])


def portfolio_returns(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted daily portfolio returns from an aligned returns panel.

    ``returns`` columns must include the tradable ``TICKERS``.
    """
    w = weights_vector(weights)
    asset_returns = returns[[*TICKERS]].to_numpy(dtype=float)
    pr = asset_returns @ w
    return pd.Series(pr, index=returns.index, name="portfolio")

def cumulative_equity(returns: pd.Series, start: float = 100.0) -> pd.Series:
    """Compound daily returns into an equity curve normalized to ``start``."""
    return start * (1.0 + returns).cumprod()