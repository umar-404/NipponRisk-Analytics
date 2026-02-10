# NipponRisk Analytics
"""HTTP routes: ``POST /api/analyze`` and ``GET /api/health``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas import AnalysisResult, HealthResponse, PortfolioInput
from app.services.analysis import health_payload, run_analysis

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalysisResult)
def analyze(payload: PortfolioInput) -> dict:
    """Run the risk engine for the given portfolio weights.

    Request body: ``{"weights": {"7203.T": 0.25, ...}}`` (any scale; normalized).
    Returns VaR (historical + Monte Carlo), max drawdown, betas, and stress-test
    projections for the Aug 2024 and Mar 2020 shocks.
    """
    try:
        return run_analysis(payload.weights)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Liveness + data freshness."""
    try:
        return health_payload()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc