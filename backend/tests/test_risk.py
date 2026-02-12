# NipponRisk Analytics
"""Offline unit tests for the quantitative risk engine.

Uses synthetic, deterministically-constructed returns panels so every metric is
verifiable by hand (no network, no randomness except the seeded Monte Carlo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import STRESS_WINDOWS, TICKERS
from app.risk.beta import asset_betas, portfolio_beta
from app.risk.drawdown import cumulative_equity, drawdown_series, max_drawdown
from app.risk.monte_carlo import estimate_moments, monte_carlo_var
from app.risk.portfolio import normalize_weights, portfolio_returns, weights_vector
from app.risk.stress import slice_window, stress_test_all, stress_test_window
from app.risk.var import historical_var


def _returns_panel(asset_drifts: dict[str, float], start: str = "2019-01-01", n: int = 520) -> pd.DataFrame:
    """Build a returns panel spanning Jan 2019 so it covers the 2020 COVID window.

    Each tradable asset = bench * beta + small drift; benchmark is a seeded
    random series. asset_drifts maps ticker -> beta-ish multiplier.
    """
    idx = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(123)
    bench = rng.normal(0.0004, 0.011, n)
    data: dict[str, np.ndarray] = {BENCH: bench}
    for t in TICKERS:
        data[t] = asset_drifts.get(t, 1.0) * bench + rng.normal(0.0, 0.002, n)
    return pd.DataFrame(data, index=idx)


BENCH = "^N225"
WEIGHTS = {TICKERS[0]: 0.4, TICKERS[1]: 0.3, TICKERS[2]: 0.2, TICKERS[3]: 0.1}


# --------------------------------------------------------------------------- #
# portfolio weights
# --------------------------------------------------------------------------- #
def test_normalize_weights_renormalizes_negatives():
    w = normalize_weights({"7203.T": 0.5, "6758.T": -0.2, "8306.T": 0.5})
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["6758.T"] == 0.0  # negatives clipped


def test_normalize_weights_equal_fallback():
    w = normalize_weights({})
    assert sum(w.values()) == pytest.approx(1.0)
    assert set(w) == set(TICKERS)
    assert len({round(v, 6) for v in w.values()}) == 1


def test_normalize_weights_ignores_unknown():
    w = normalize_weights({"7203.T": 1.0, "AAPL": 5.0})
    assert set(w) == set(TICKERS)
    assert w["7203.T"] == pytest.approx(1.0)


def test_weights_vector_order():
    v = weights_vector({TICKERS[0]: 1.0})
    assert v[0] == pytest.approx(1.0)
    assert np.sum(np.abs(v[1:])) == pytest.approx(0.0)


def test_portfolio_returns_weights_average():
    rng = np.random.default_rng(5)
    n = 10
    df = pd.DataFrame({t: rng.uniform(-0.01, 0.01, n) for t in TICKERS})
    pr = portfolio_returns(df, WEIGHTS)
    manual = (df[TICKERS].to_numpy() @ np.array(list(WEIGHTS.values()))).reshape(-1)
    np.testing.assert_allclose(pr.to_numpy(), manual)


# --------------------------------------------------------------------------- #
# VaR
# --------------------------------------------------------------------------- #
def test_historical_var_positive_and_ordered():
    panel = _returns_panel({}, n=1200)
    var = historical_var(panel, WEIGHTS, (0.95, 0.99))
    assert all(v >= 0 for v in var.values())
    assert var[0.99] > var[0.95]  # higher confidence -> larger loss quantile


def test_historical_var_known_series():
    n = 100
    idx = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(9)
    base = rng.normal(0.0, 0.02, n)
    df = pd.DataFrame({**{t: base for t in TICKERS}, BENCH: np.zeros(n)}, index=idx)
    var = historical_var(df, {t: 1.0 / len(TICKERS) for t in TICKERS}, (0.95,))
    expected = -np.percentile(base, 5.0)
    assert var[0.95] == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# Monte Carlo
# --------------------------------------------------------------------------- #
def _mc_params(n=5000, seed=42):
    from app.config import MonteCarloParams
    return MonteCarloParams(n_scenarios=n, confidence_levels=(0.95, 0.99), random_seed=seed)


def test_mc_var_is_positive_reproducible():
    panel = _returns_panel({}, n=1200)
    p = _mc_params()
    v1 = monte_carlo_var(panel, WEIGHTS, p)
    v2 = monte_carlo_var(panel, WEIGHTS, _mc_params())
    for cl in (0.95, 0.99):
        assert v1[cl] > 0
        assert v1[cl] == pytest.approx(v2[cl])  # seeded -> reproducible
    assert v1[0.99] > v1[0.95]


def test_estimate_moments_shape():
    import app.risk.monte_carlo as mcm
    panel = _returns_panel({}, n=300)
    mu, sigma = mcm.estimate_moments(panel)
    assert mu.shape == (len(TICKERS),)
    assert sigma.shape == (len(TICKERS), len(TICKERS))
    assert np.all(np.linalg.eigvalsh(sigma) > -1e-12)  # PSD


# --------------------------------------------------------------------------- #
# Drawdown
# --------------------------------------------------------------------------- #
def test_max_drawdown_known_series():
    ret = pd.Series([0.0, -0.50, 0.50, 0.25])
    assert max_drawdown(ret) == pytest.approx(-0.50)


def test_drawdown_series_never_positive():
    rng = np.random.default_rng(3)
    ret = pd.Series(rng.normal(0.000, 0.02, 200))
    dd = drawdown_series(ret)
    assert (dd <= 1e-12).all()


def test_cumulative_equity_start_normalized():
    eq = cumulative_equity(pd.Series([0.1, -0.1]), start=100.0)
    assert eq.iloc[0] == pytest.approx(110.0)
    assert eq.iloc[1] == pytest.approx(99.0)


# --------------------------------------------------------------------------- #
# Beta
# --------------------------------------------------------------------------- #
def test_asset_beta_exact_relationship():
    n = 500
    rng = np.random.default_rng(11)
    bench = rng.normal(0.0, 0.01, n)
    df = pd.DataFrame(
        {TICKERS[0]: 2.0 * bench, **{t: bench for t in TICKERS[1:]}, BENCH: bench}
    )
    betas = asset_betas(df)
    assert betas[TICKERS[0]] == pytest.approx(2.0, abs=1e-9)
    for t in TICKERS[1:]:
        assert betas[t] == pytest.approx(1.0, abs=1e-9)


def test_portfolio_beta_weighted_average():
    panel = _returns_panel({t: (i + 1) for i, t in enumerate(TICKERS)}, n=800)
    ab = asset_betas(panel)
    w = weights_vector(WEIGHTS)
    manual = sum(ab[t] * w[i] for i, t in enumerate(TICKERS))
    assert portfolio_beta(panel, WEIGHTS) == pytest.approx(manual)


# --------------------------------------------------------------------------- #
# Stress testing
# --------------------------------------------------------------------------- #
def test_stress_windows_slice_dates():
    panel = _returns_panel({}, n=1500)
    covid = STRESS_WINDOWS[1]
    wslice = slice_window(panel, covid)
    assert (wslice.index >= pd.Timestamp(covid.start)).all()
    assert (wslice.index <= pd.Timestamp(covid.end)).all()
    assert len(wslice) > 0


def test_stress_test_all_returns_expected_keys():
    panel = _returns_panel({}, n=1500)  # covers 2020
    results = stress_test_all(panel, WEIGHTS)
    assert len(results) == len(STRESS_WINDOWS)
    for r in results:
        assert r["projected_drawdown"] > 0  # positive loss figure
        assert "total_return" in r
        assert r["n_obs"] > 0


def test_stress_window_empty_raises():
    panel = _returns_panel({}, n=30)  # too short for COVID window
    covid = STRESS_WINDOWS[1]
    with pytest.raises(ValueError):
        stress_test_window(panel, WEIGHTS, covid)