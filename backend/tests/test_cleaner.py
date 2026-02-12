# NipponRisk Analytics
"""Offline unit tests for the data-cleaning pipeline (no network needed).

These exercise :mod:`app.data.cleaner` against synthetic price frames so the
cleaning, alignment, and return math are deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import ALL_SYMBOLS, BENCHMARK, TICKERS
from app.data.cleaner import (
    _drop_non_positive_prices,
    build_clean_dataset,
    build_panel,
    compute_returns,
    drop_non_trading_rows,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def synthetic_long() -> pd.DataFrame:
    """A long-format frame covering all 4 tickers + benchmark over 10 days.

    Prices rise deterministically with a few deliberate artifacts: a zero price
    for Sony and a trailing NaN for MUFG to exercise the clean-up paths.
    """
    dates = pd.bdate_range("2024-01-01", periods=10)
    symbols = ALL_SYMBOLS
    rows: list[dict] = []
    for i, date in enumerate(dates):
        for j, sym in enumerate(symbols):
            # Base price rises ~2%/day, offset per symbol so columns differ.
            base = 100.0 + 2.0 * i + 5.0 * j
            if sym == "6758.T" and i == 3:
                base = 0.0  # artifact: zero price for Sony on day 3
            rows.append({"date": date, "ticker": sym, "adj_close": base})
    df = pd.DataFrame(rows)
    # Add a NaN at the end for MUFG to simulate a missing last obs.
    df.loc[(df["ticker"] == "8306.T") & (df["date"] == dates[-1]), "adj_close"] = np.nan
    return df


@pytest.fixture
def growth_long() -> pd.DataFrame:
    """Clean steadily-growing prices with NO in-sample artifacts.

    Every symbol grows ~2%/day and there are no zero/NaN values until a single
    trailing NaN, so the return series is clean single-step ~2%.
    """
    dates = pd.bdate_range("2024-01-01", periods=10)
    symbols = ALL_SYMBOLS
    rows: list[dict] = []
    for i, date in enumerate(dates):
        for j, sym in enumerate(symbols):
            base = 100.0 + 2.0 * i + 5.0 * j
            rows.append({"date": date, "ticker": sym, "adj_close": base})
    df = pd.DataFrame(rows)
    df.loc[(df["ticker"] == "8306.T") & (df["date"] == dates[-1]), "adj_close"] = np.nan
    return df


# --------------------------------------------------------------------------- #
# build_panel
# --------------------------------------------------------------------------- #
def test_build_panel_has_all_symbols(synthetic_long):
    panel = build_panel(synthetic_long)
    assert list(panel.columns) == ALL_SYMBOLS
    assert isinstance(panel.index, pd.DatetimeIndex)


def test_build_panel_treats_zero_as_missing(synthetic_long):
    panel = build_panel(synthetic_long)
    sony = panel["6758.T"]
    # Day index 3 is a business day offset from the aligned panel's provision.
    assert (sony[sony.index == sony.index[3]] <= 0).sum() == 0
    # Zero got dropped -> that date is NaN for Sony; forward-fill later.
    assert sony.isna().sum() >= 1


def test_build_panel_raises_on_empty():
    with pytest.raises(ValueError):
        build_panel(pd.DataFrame())


# --------------------------------------------------------------------------- #
# Alignment
# --------------------------------------------------------------------------- #
def test_drop_non_trading_rows_inner_joins(synthetic_long):
    panel = build_panel(synthetic_long)
    aligned = drop_non_trading_rows(panel)
    # MUFG (8306.T) is NaN on the last day -> that row is dropped for everyone.
    assert aligned.index.max() < panel.index.max()
    assert aligned.notna().all().all()


# --------------------------------------------------------------------------- #
# compute_returns
# --------------------------------------------------------------------------- #
def test_compute_returns_simple_growth(growth_long):
    panel = build_panel(growth_long)
    aligned = drop_non_trading_rows(panel)
    ret = compute_returns(aligned)
    # ~2% daily growth -> returns roughly +0.02 during the clean stretch.
    toyota = ret["7203.T"].iloc[1:5]
    assert (toyota > 0.015).all() and (toyota < 0.03).all()


def test_compute_returns_is_aligned(synthetic_long):
    panel = build_panel(synthetic_long)
    aligned = drop_non_trading_rows(panel)
    ret = compute_returns(aligned)
    assert ret.notna().all().all()
    assert (ret.index == aligned.index[1:]).all()


def test_compute_returns_first_row_dropped(synthetic_long):
    panel = build_panel(synthetic_long)
    aligned = drop_non_trading_rows(panel)
    ret = compute_returns(aligned)
    assert len(ret) == len(aligned) - 1


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def test_drop_non_positive_prices():
    s = pd.Series([100.0, 0.0, -5.0, 102.0, np.nan])
    cleaned = _drop_non_positive_prices(s)
    assert list(cleaned.dropna()) == [100.0, 102.0]


def test_benchmark_present_check(synthetic_long):
    aligned, ret = build_clean_dataset(synthetic_long)["prices"], None
    ret2 = compute_returns(aligned)
    from app.data.cleaner import assert_benchmark_present

    assert_benchmark_present(ret2)  # should not raise
    with pytest.raises(ValueError):
        assert_benchmark_present(ret2.drop(columns=[BENCHMARK]))


# --------------------------------------------------------------------------- #
# End-to-end
# --------------------------------------------------------------------------- #
def test_build_clean_dataset_shapes(synthetic_long):
    out = build_clean_dataset(synthetic_long)
    prices, ret = out["prices"], out["returns"]
    assert set(ret.columns) >= set(TICKERS + [BENCHMARK])
    assert len(ret) == len(prices) - 1
    assert ret.notna().all().all()