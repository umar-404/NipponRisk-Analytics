# NipponRisk Analytics
"""Cleaning, alignment, and return computation for price data.

Given the raw long-form frame from :mod:`app.data.fetcher`, this module:
1. Rejects zero/non-positive price artifacts.
2. Pivots to a wide ``date x symbol`` adjusted-close panel.
3. Aligns trading days across all assets + benchmark (inner-join on dates).
4. Computes simple daily percentage returns.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.config import ALL_SYMBOLS, BENCHMARK, MIN_TRADING_DAYS

logger = logging.getLogger(__name__)


def build_panel(long_df: pd.DataFrame, symbols: list[str] | None = None) -> pd.DataFrame:
    """Convert the tidy frame into a wide date x symbol adjusted-close panel.

    Parameters
    ----------
    long_df : pandas.DataFrame
        Columns ``['date', 'ticker', 'adj_close']`` (from the fetcher).
    symbols : list[str] | None
        Columns to retain (defaults to the configured universe).

    Returns
    -------
    pandas.DataFrame
        Index = normalized ``datetime64[ns]`` dates, columns = symbols,
        values = adjusted close. Fully numeric; invalid prices dropped.
    """
    cols = symbols or ALL_SYMBOLS
    if long_df.empty:
        raise ValueError("Cannot build a panel from empty price data.")

    df = long_df.copy()
    df["date"] = pd.DatetimeIndex(df["date"])
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_localize(None)  # tz-naive dates
    df["date"] = df["date"].dt.normalize()
    df = df[df["ticker"].isin(cols)]

    panel = df.pivot(index="date", columns="ticker", values="adj_close")
    panel = panel[cols].reindex(columns=cols)  # enforce column order

    panel = panel.apply(_drop_non_positive_prices, axis=0)
    panel.index.name = "date"

    _warn_on_missing_cols(panel, cols)
    return panel[cols]


def drop_non_trading_rows(panel: pd.DataFrame, symbols: list[str] | None = None) -> pd.DataFrame:
    """Align trading days across symbols via inner-join.

    Removes dates where any asset/benchmark is missing so every column shares
    the same row index (an important precondition for joint risk math).
    """
    cols = symbols or ALL_SYMBOLS
    returns = panel[cols].dropna(how="all")
    # Drop rows that are missing in *any* of the requested symbols to keep all
    # columns contemporaneous (required for covariance / portfolio returns).
    return returns.loc[returns[cols].notna().all(axis=1)]


def compute_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Simple daily percentage returns (as decimals): ``r_t = P_t / P_{t-1} - 1``.

    The first row becomes NaN (no prior price) and is dropped.
    """
    returns = panel.diff() / panel.shift(1)  # simple returns, avoids pct_change fill_method API drift
    returns = returns.mask(~np.isfinite(returns))  # inf/nan -> nan
    returns = returns.dropna(how="all")
    # Drop leading NaNs so the returns panel starts where every symbol has a value.
    returns = returns.loc[returns.notna().all(axis=1)]
    returns.index.name = "date"
    return returns


def build_clean_dataset(long_df: pd.DataFrame, symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """End-to-end clean: panel -> aligned panel -> returns.

    Returns
    -------
    dict
        ``{"prices": aligned_close, "returns": aligned_returns}`` where both
        frames are aligned on the same date index (assets + benchmark).
    """
    cols = symbols or ALL_SYMBOLS
    panel = build_panel(long_df, cols)
    panel = drop_non_trading_rows(panel, cols)
    if len(panel) < MIN_TRADING_DAYS:
        logger.warning(
            "Aligned panel only has %d rows (min expected %d). "
            "The lookback may be short or coverage poor.",
            len(panel),
            MIN_TRADING_DAYS,
        )
    returns = compute_returns(panel)
    return {"prices": panel, "returns": returns}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _drop_non_positive_prices(series: pd.Series) -> pd.Series:
    """Drop zero/negative prices (yfinance artifacts) from a price column."""
    cleaned = series[~(series <= 0)]
    n_dropped = int(series.notna().sum() - cleaned.notna().sum())
    if n_dropped:
        logger.warning(
            "Dropped %d non-positive price rows for %s",
            n_dropped,
            series.name,
        )
    return cleaned


def _warn_on_missing_cols(panel: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in panel.columns or panel[c].isna().all()]
    if missing:
        logger.warning("The following symbols returned no usable prices: %s", missing)


# Small convenience re-exports used by scripts
def aligned_returns_dataset(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(aligned_close, aligned_returns)`` from a raw long frame."""
    out = build_clean_dataset(long_df)
    return out["prices"], out["returns"]


def assert_benchmark_present(returns: pd.DataFrame) -> None:
    """Raise if the benchmark column is missing from a returns panel."""
    if BENCHMARK not in returns.columns:
        raise ValueError(
            f"Benchmark {BENCHMARK} missing from returns panel; cannot compute beta."
        )