# NipponRisk Analytics
"""Pydantic request/response models for the public API.

Conventions:
- Weights arrive per tradable ticker (any scale) and are normalized server-side.
- The benchmark `^N225` is never a user-weightable position; it is the beta and
  stress reference only.
- Risk figures (VaR, drawdowns, stress) are returned as **positive decimal
  losses**, e.g. ``0.023`` meaning a 2.3% expected loss over the horizon.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import TICKERS


class PortfolioInput(BaseModel):
    """POST /api/analyze request body."""

    weights: dict[str, float] = Field(
        description="Weights per tradable ticker; any scale, normalized server-side.",
    )
    risk_free_rate: float = 0.0  # reserved future use (Sharpe etc.)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        for t in v:
            if t not in TICKERS:
                raise ValueError(f"Unknown ticker '{t}'. Allowed: {TICKERS}")
            if not isinstance(v[t], (int, float)):
                raise ValueError(f"Weight for '{t}' must be numeric.")
        return v


class VaRResult(BaseModel):
    """VaR for a single methodology (95% and 99%, 1-day horizon)."""

    p95: float = Field(description="95% VaR as a positive decimal daily loss")
    p99: float = Field(description="99% VaR as a positive decimal daily loss")


class VarBlock(BaseModel):
    historical: VaRResult
    monte_carlo: VaRResult


class StressResult(BaseModel):
    key: str
    label: str
    start: str
    end: str
    event: str = ""
    projected_drawdown: float | None = Field(
        description="Projected portfolio max drawdown over the window (positive loss), None if skipped"
    )
    total_return: float | None
    n_obs: int
    skipped: bool = False
    note: str = ""


class AnalysisResult(BaseModel):
    """POST /api/analyze response body."""

    tickers: list[str]
    weights_norm: dict[str, float]
    dates: list[str]
    portfolio_returns: list[float]
    benchmark_returns: list[float]
    equity_curve: list[float]
    benchmark_equity: list[float]
    var: VarBlock
    max_drawdown: float
    asset_betas: dict[str, float]
    portfolio_beta: float
    stress: list[StressResult]
    data_start: str
    data_end: str
    n_obs: int


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    n_obs: int
    data_start: str
    data_end: str
    cache_seconds: int