# NipponRisk Analytics
"""Demo the data pipeline end-to-end **without network**.

Generates a small synthetic long-format price frame (mirroring what the real
yfinance fetcher returns), then runs it through ``build_clean_dataset`` to show
the aligned price + returns panels. Useful for a quick smoke test offline.

Usage:
    python scripts/demo_clean_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ALL_SYMBOLS  # noqa: E402
from app.data.cleaner import build_clean_dataset, compute_returns  # noqa: E402


def make_synthetic_prices(n_days: int = 300, seed: int = 7) -> pd.DataFrame:
    """Build a long-format frame styled like the fetcher output."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    base = {"7203.T": 2200.0, "6758.T": 12000.0, "8306.T": 900.0, "9432.T": 150.0, "^N225": 28000.0}
    rows: list[dict] = []
    price = {s: v for s, v in base.items()}
    for date in dates:
        for sym in ALL_SYMBOLS:
            daily = rng.normal(0.0006, 0.012) if sym != "^N225" else rng.normal(0.0004, 0.010)
            price[sym] *= 1.0 + daily
            rows.append({"date": date, "ticker": sym, "adj_close": price[sym]})
    return pd.DataFrame(rows)


def main() -> int:
    print("=== NipponRisk offline pipeline demo (synthetic data) ===\n")
    raw = make_synthetic_prices()
    print(f"Raw long frame: {len(raw):,} rows, {raw['ticker'].nunique()} symbols\n")

    out = build_clean_dataset(raw)
    prices, returns = out["prices"], out["returns"]

    print("Aligned prices (tail):")
    with pd.option_context("display.width", 140, "display.float_format", lambda v: f"{v:,.1f}"):
        print(prices.tail(4))
    print("\nAligned returns (tail, as %):")
    with pd.option_context("display.width", 140, "display.float_format", lambda v: f"{v:+.2%}"):
        print(returns.tail(4))

    # Sanity metrics
    vols = returns.std(ddof=1)
    print("\nSample volatility (annualized):")
    ann = 252 ** 0.5
    for sym in ALL_SYMBOLS:
        print(f"  {sym:>7}  {vols[sym]*ann:6.2%}")
    print(f"\nSharpe-style stat via clean returns: OK "
          f"(rows={len(returns)}, cols={returns.shape[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())