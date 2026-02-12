# NipponRisk Analytics
"""Offline unit tests for the yfinance fetcher's reshaping logic.

The network call is mocked out; we only verify that :func:`_melt_closes` turns
the yfinance (possibly MultiIndex) output into a tidy long frame for both the
modern ('Close' folded adjustment) and legacy ('Adj Close') column schemes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.fetcher import _melt_closes

SYMBOLS = ["7203.T", "6758.T", "8306.T", "9432.T", "^N225"]
DATES = pd.bdate_range("2024-01-01", periods=4)


def _build_multiindex_df(field: str) -> pd.DataFrame:
    """Build a yfinance-style 2-level column DataFrame."""
    cols = pd.MultiIndex.from_product([SYMBOLS, ["Open", "High", "Low", field, "Volume"]])
    rng = np.random.default_rng(1)
    data = pd.DataFrame(rng.uniform(100, 500, size=(len(DATES), len(cols))), index=DATES, columns=cols)
    return data


def test_melt_closes_uses_close_when_no_adj_close():
    df = _build_multiindex_df("Close")  # modern yfinance: adjustment in 'Close'
    out = _melt_closes(df, SYMBOLS)
    assert list(out.columns) == ["date", "ticker", "adj_close"]
    assert set(out["ticker"].unique()) == set(SYMBOLS)
    # Long frame is grouped by ticker -> dates monotonic within each ticker.
    assert out.groupby("ticker")["date"].apply(lambda s: s.is_monotonic_increasing).all()
    assert out["date"].dt.tz is None  # tz-naive normalized dates
    assert out["adj_close"].notna().all()


def test_melt_closes_uses_adj_close_when_present():
    df = _build_multiindex_df("Adj Close")  # legacy yfinance
    out = _melt_closes(df, SYMBOLS)
    assert set(out["ticker"].unique()) == set(SYMBOLS)
    assert out["adj_close"].notna().all()


def test_melt_closes_matches_close_values():
    df = _build_multiindex_df("Close")
    out = _melt_closes(df, SYMBOLS)
    # Spot check: first symbol's first-day close appears once.
    first = out[out["ticker"] == SYMBOLS[0]].iloc[0]
    assert first["adj_close"] == df[(SYMBOLS[0], "Close")].iloc[0]


def test_melt_closes_drops_nan_rows():
    df = _build_multiindex_df("Close")
    df.loc[DATES[0], (SYMBOLS[1], "Close")] = np.nan  # inject a NaN price
    out = _melt_closes(df, SYMBOLS)
    assert out["adj_close"].notna().all()
    # Sony's first-observation row is gone, but it still has later obs.
    sony = out[out["ticker"] == SYMBOLS[1]]
    assert len(sony) == len(DATES) - 1