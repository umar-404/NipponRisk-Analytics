# NipponRisk Analytics
"""Application-level configuration: asset universe, lookback, paths, stress windows.

This module is the single source of truth for the tickers, benchmark, data
cache location, and the historical stress-test windows.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Asset universe
# --------------------------------------------------------------------------- #
TICKERS: list[str] = [
    "7203.T",  # Toyota
    "6758.T",  # Sony Group
    "8306.T",  # Mitsubishi UFJ Financial Group
    "9432.T",  # NTT
]

BENCHMARK: str = "^N225"  # Nikkei 225

# Display names (frontend labels fall back to the ticker if absent)
TICKER_NAMES: dict[str, str] = {
    "7203.T": "Toyota",
    "6758.T": "Sony",
    "8306.T": "MUFG",
    "9432.T": "NTT",
    "^N225": "Nikkei 225",
}

# Every column used in the merged panel (assets + benchmark).
ALL_SYMBOLS: list[str] = [*TICKERS, BENCHMARK]

# --------------------------------------------------------------------------- #
# Data parameters
# --------------------------------------------------------------------------- #
# NOTE: the lookback must also cover the *earliest* defined stress window
# (March 2020 COVID). A plain "5y" back from today puts the start after that
# window, so we request a longer window by default.
PERIOD: str = "7y"      # yfinance period string for daily adjusted closes
# Expected minimum trading days over the lookback (sanity gate):
# ~250 trading days/yr -> >1200 for 5y; use a conservative floor.
MIN_TRADING_DAYS: int = 400

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_ROOT, "data")
RAW_CACHE_PATH = os.path.join(DATA_DIR, "raw_panel.parquet")
PRICES_PATH = os.path.join(DATA_DIR, "prices.parquet")
# Panel read by the API risk engine (aligned daily returns).
PANEL_PATH = os.path.join(DATA_DIR, "returns.parquet")
# Data freshness timeout: cache is considered stale after this many seconds.
CACHE_MAX_AGE_SECONDS: int = int(os.environ.get("NIPPORISK_CACHE_TTL", 60 * 60 * 24))


# --------------------------------------------------------------------------- #
# Stress-test windows (programmatic date slices)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StressWindow:
    """A hard-sliced historical window used for stress testing."""

    key: str
    label: str
    start: str  # ISO date, inclusive
    end: str    # ISO date, inclusive
    event: str = ""


STRESS_WINDOWS: tuple[StressWindow, ...] = (
    StressWindow(
        key="yen-spike-2024",
        label="Aug 2024 Yen-Spike Crash",
        start="2024-07-01",
        end="2024-08-31",
        event="Bank of Japan rate hike triggered a yen spike and one of the Nikkei's worst single-day crashes.",
    ),
    StressWindow(
        key="covid-2020",
        label="March 2020 COVID Shock",
        start="2020-01-31",
        end="2020-04-30",
        event="Global pandemic sell-off and acute market stress.",
    ),
)


# --------------------------------------------------------------------------- #
# Monte Carlo parameters
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MonteCarloParams:
    n_scenarios: int = 10_000
    confidence_levels: tuple[float, ...] = (0.95, 0.99)
    random_seed: int = 42


def as_data_config() -> dict:
    """Small helper exposing data params for scripts/tests."""
    return {
        "tickers": list(TICKERS),
        "benchmark": BENCHMARK,
        "period": PERIOD,
        "all_symbols": list(ALL_SYMBOLS),
        "raw_cache_path": RAW_CACHE_PATH,
        "panel_path": PANEL_PATH,
        "cache_max_age_seconds": CACHE_MAX_AGE_SECONDS,
        "stress_windows": [
            {
                "key": w.key,
                "label": w.label,
                "start": w.start,
                "end": w.end,
                "event": w.event,
            }
            for w in STRESS_WINDOWS
        ],
    }