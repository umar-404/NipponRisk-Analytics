# NipponRisk Analytics
"""Data access: load the cached aligned returns panel used by the API.

The panel is produced once by ``scripts/fetch_data.py`` and cached to parquet so
the API doesn't hit yfinance on every request. This module loads it and
normalizes the index to tz-naive dates regardless of how it was stored.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import PANEL_PATH


def load_returns_panel(path: str | Path = PANEL_PATH) -> pd.DataFrame:
    """Load the cached aligned returns panel as a tz-naive date-indexed frame."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Returns panel not found at {p}. Run `scripts/fetch_data.py` first."
        )
    df = pd.read_parquet(p)
    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    df.index.name = "date"
    return df