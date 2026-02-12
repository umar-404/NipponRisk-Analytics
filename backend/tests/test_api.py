# NipponRisk Analytics
"""API contract tests for `POST /api/analyze` and `GET /api/health`.

These use a synthetic returns panel injected via dependency-free patching of the
loader, so no network is required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import BENCHMARK, TICKERS
from app.main import app
from app.services import analysis as service

client = TestClient(app)

BENCH = BENCHMARK


@pytest.fixture
def synthetic_returns() -> pd.DataFrame:
    """A short synthetic aligned returns panel (5 symbols)."""
    n = 220
    idx = pd.bdate_range("2021-06-01", periods=n)
    rng = np.random.default_rng(2024)
    bench = rng.normal(0.0004, 0.011, n)
    data = {BENCH: bench}
    for t in TICKERS:
        data[t] = bench + rng.normal(0.0, 0.002, n)
    return pd.DataFrame(data, index=idx)


@pytest.fixture(autouse=True)
def _inject_panel(synthetic_returns, monkeypatch):
    """Use the synthetic panel for all service loads during tests."""

    def fake_load(*args, **kwargs):
        return synthetic_returns

    monkeypatch.setattr(service, "load_returns_panel", fake_load)


def _weight_map():
    return {t: 0.25 for t in TICKERS}


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["n_obs"] == 220
    assert body["data_start"] < body["data_end"]


# --------------------------------------------------------------------------- #
# Analyze
# --------------------------------------------------------------------------- #
def test_analyze_valid_weights():
    r = client.post("/api/analyze", json={"weights": _weight_map()})
    assert r.status_code == 200
    body = r.json()
    assert list(body["tickers"]) == TICKERS
    assert abs(sum(body["weights_norm"].values()) - 1.0) < 1e-6
    assert body["n_obs"] == synthetic_len() - 1 or body["n_obs"] > 100
    assert len(body["dates"]) == len(body["portfolio_returns"])
    # VaR blocks present and positive.
    for method in ("historical", "monte_carlo"):
        assert body["var"][method]["p95"] > 0
        assert body["var"][method]["p99"] > 0
        assert body["var"][method]["p99"] >= body["var"][method]["p95"]
    assert body["max_drawdown"] <= 0
    assert isinstance(body["asset_betas"], dict)
    assert len(body["stress"]) >= 1


def test_analyze_unknown_ticker_400():
    r = client.post("/api/analyze", json={"weights": {"7203.T": 1.0, "AAPL": 1.0}})
    assert r.status_code == 422  # pydantic validation error


def test_analyze_normalizes_weights():
    r = client.post("/api/analyze", json={"weights": {"7203.T": 50, "6758.T": 50}})
    assert r.status_code == 200
    wn = r.json()["weights_norm"]
    assert wn["7203.T"] == wn["6758.T"] == pytest.approx(0.5)


def test_analyze_bad_payload():
    r = client.post("/api/analyze", json={"nope": 1})
    assert r.status_code == 422


def test_benchmark_return_series_present():
    r = client.post("/api/analyze", json={"weights": _weight_map()})
    body = r.json()
    assert len(body["benchmark_returns"]) == len(body["dates"])
    assert len(body["equity_curve"]) == len(body["dates"])


def synthetic_len():
    return 220