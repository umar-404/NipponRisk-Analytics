# NipponRisk Analytics
"""Fetch, clean, and persist the 4 Japanese tickers + Nikkei 225 benchmark.

Usage:
    python scripts/fetch_data.py [--period 5y] [--out DIR]

Produces two parquet files in the data dir:
- ``prices.parquet``   : wide aligned adjusted-close panel (date x symbol)
- ``returns.parquet``  : wide aligned simple daily returns, as decimals

The risk engine reads ``returns.parquet`` for joint portfolio math.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Allow running as `python scripts/fetch_data.py` from anywhere without
# installing the package by adding the backend root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import PANEL_PATH, PERIOD, TICKER_NAMES, TICKERS, BENCHMARK  # noqa: E402
from app.data.cleaner import build_clean_dataset  # noqa: E402
from app.data.fetcher import download_adj_close_prices, save_raw_cache  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default=PERIOD, help="yfinance period (default: %(default)s)")
    parser.add_argument("--out", default=None, help="Output directory (default: backend/data)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("fetch_data")

    logger.info("Universe: %s | benchmark: %s", TICKERS, BENCHMARK)
    logger.info("Fetching %s of daily adjusted closes...", args.period)
    long_df = download_adj_close_prices(period=args.period)

    out = build_clean_dataset(long_df)
    prices, returns = out["prices"], out["returns"]
    logger.info("Fetched %d raw rows total.", len(long_df))
    logger.info("Aligned prices: %d rows x %d symbols", prices.shape[0], prices.shape[1])
    logger.info("Aligned returns: %d rows x %d symbols", returns.shape[0], returns.shape[1])

    if prices.shape[0] < 10:
        logger.error("Insufficient data — refusing to write a near-empty panel.")
        return 1

    out_dir = Path(args.out) if args.out else Path(PANEL_PATH).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    prices_path = out_dir / "prices.parquet"
    returns_path = out_dir / "returns.parquet"
    prices.to_parquet(prices_path)
    returns.to_parquet(returns_path)
    logger.info("Wrote aligned prices  -> %s", prices_path)
    logger.info("Wrote aligned returns -> %s", returns_path)

    save_raw_cache(long_df)

    print("\n=== Aligned prices (last 5 rows) ===")
    with pd.option_context("display.width", 140):
        print(prices.tail())

    print("\n=== Aligned returns (last 5 rows) ===")
    with pd.option_context(
        "display.width", 140, "display.float_format", lambda v: f"{v:+.4%}"
    ):
        print(returns.tail())

    print("\n=== Tickers ===")
    for t in TICKERS:
        print(f"  {t:>7}  {TICKER_NAMES.get(t, t)}: {int(prices[t].notna().sum())} obs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())