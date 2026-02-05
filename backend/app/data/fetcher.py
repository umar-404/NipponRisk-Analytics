# NipponRisk Analytics
"""yfinance data acquisition for the 4 Japanese tickers + Nikkei 225 benchmark.

Responsibilities:
- Download 5 years of daily **adjusted close** prices via ``yfinance``.
- Return a tidy long-form DataFrame: columns ``['date', 'ticker', 'adj_close']``.
- Optionally cache to a parquet file to avoid hitting yfinance on every run.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from app.config import ALL_SYMBOLS, DATA_DIR, PERIOD, RAW_CACHE_PATH

logger = logging.getLogger(__name__)


def download_adj_close_prices(period: str = PERIOD, tickers: list[str] | None = None):
    """Download daily adjusted close prices for the configured universe.

    Parameters
    ----------
    period : str
        yfinance period string (e.g. ``"5y"``).
    tickers : list[str] | None
        Override the configured ticker list (mostly for tests).

    Returns
    -------
    pandas.DataFrame
        Long-form frame with columns ``['date', 'ticker', 'adj_close']``
        where ``date`` is a ``datetime64[ns]`` dtype normalized to midnight UTC.
    """
    symbols = tickers or ALL_SYMBOLS
    df = _download_with_retries(period=period, symbols=symbols)
    return _melt_closes(df, symbols=symbols)


def _download_with_retries(
    period: str, symbols: list[str], retries: int = 3, backoff_seconds: float = 5.0
):
    """Call ``yf.download`` with simple linear backoff on transient failures."""
    import yfinance as yf  # deferred import: yfinance is heavy / can be missing

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            logger.info("Fetching %d symbols (period=%s) — attempt %d/%d",
                        len(symbols), period, attempt, retries)
            df = yf.download(
                tickers=symbols,
                period=period,
                interval="1d",
                auto_adjust=True,      # use adjusted close (splits + dividends)
                group_by="ticker",     # columns: ('TICKER', 'Adj Close')
                threads=True,
                progress=False,
            )
            if df is None or df.empty:
                raise RuntimeError("yfinance returned an empty DataFrame")
            return df
        except Exception as exc:  # noqa: BLE001 — surface after retries
            last_exc = exc
            logger.warning("yfinance download attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise RuntimeError(f"yfinance download failed after {retries} attempts: {last_exc}")


def _melt_closes(df: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Extract adjusted-close columns from yfinance output and tidy the frame.

    yfinance returns columns as a MultiIndex ``('TICKER', 'Adj Close')`` when
    ``group_by='ticker'``. We select only the ``'Adj Close'`` level, stack into
    long form, and normalize the index to midnight-UTC dates.
    """
    if df.columns.nlevels > 1:
        # yfinance >= 0.2.4x folds adjustment into 'Close'; older versions emit
        # a separate 'Adj Close'. Pick whichever price field exists.
        price_levels = set(df.columns.get_level_values(1).tolist())
        field = "Adj Close" if "Adj Close" in price_levels else "Close"
        if field not in price_levels:
            raise KeyError(
                f"yfinance output has no {field!r}/'Adj Close' price column; "
                f"got levels {sorted(price_levels)}"
            )
        adj_close = df.xs(field, axis=1, level=1)
    else:
        # Single ticker path — column may be 'Adj Close' or 'Close'.
        field = "Adj Close" if "Adj Close" in df.columns else "Close"
        adj_close = df[[field]]

    adj_close.index = pd.DatetimeIndex(adj_close.index)
    if adj_close.index.tz is not None:
        adj_close.index = adj_close.index.tz_localize(None)  # tz-naive dates
    adj_close.index = adj_close.index.normalize()
    adj_close.index.name = "date"

    long = adj_close.reset_index().melt(
        id_vars=["date"], var_name="ticker", value_name="adj_close"
    )
    long = long.dropna(subset=["adj_close"])
    long["ticker"] = long["ticker"].astype(str)
    return long[["date", "ticker", "adj_close"]].reset_index(drop=True)


def load_cached_raw(path: str | Path = RAW_CACHE_PATH) -> pd.DataFrame | None:
    """Load a previously cached raw panel if present."""
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["date"] = pd.DatetimeIndex(df["date"])
    return df


def save_raw_cache(df: pd.DataFrame, path: str | Path = RAW_CACHE_PATH) -> Path:
    """Persist a raw long frame to parquet (creates the data dir if needed)."""
    p = Path(path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    logger.info("Wrote raw cache to %s", p)
    return p


def ensure_data_dir() -> Path:
    """Create the backend data directory and return its path."""
    d = Path(DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d