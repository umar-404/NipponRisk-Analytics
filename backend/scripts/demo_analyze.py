# NipponRisk Analytics
"""Run a sample weighted analysis offline against the cached returns panel.

Reads ``backend/data/returns.parquet`` (produced by :file:`fetch_data.py`) and
prints historical + Monte Carlo VaR, max drawdown, betas, and the stress-test
projections for a given weight mix.

Usage:
    python scripts/demo_analyze.py [--data PATH] [--w A B C D]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import PANEL_PATH, STRESS_WINDOWS, TICKERS  # noqa: E402
from app.risk.beta import asset_betas, portfolio_beta  # noqa: E402
from app.risk.drawdown import portfolio_max_drawdown  # noqa: E402
from app.risk.monte_carlo import monte_carlo_var  # noqa: E402
from app.risk.stress import stress_test_all  # noqa: E402
from app.risk.var import historical_var  # noqa: E402


def load_returns(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)  # tz-naive dates
    df.index = df.index.normalize()
    df.index.name = "date"
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=f"{Path(PANEL_PATH).parent / 'returns.parquet'}")
    parser.add_argument(
        "--w", nargs=4, type=float,
        default=[0.25, 0.25, 0.25, 0.25],
        metavar=("A", "B", "C", "D"),
        help="Weights for Toyota, Sony, MUFG, NTT (any scale; normalized).",
    )
    args = parser.parse_args(argv)

    returns = load_returns(args.data)
    weights = {t: w for t, w in zip(TICKERS, args.w)}
    norm = {t: w / sum(args.w) for t, w in weights.items()}  # normalize for display

    print(f"returns panel: {returns.shape[0]} rows | "
          f"{returns.index.min().date()} -> {returns.index.max().date()}")
    print(f"weights (normalized): { {t: round(v, 4) for t, v in norm.items()} }")

    print("\n--- Risk metrics (1-day) ---")
    hvar = historical_var(returns, weights)
    mcvar = monte_carlo_var(returns, weights)
    print(f"Historical VaR : 95% {hvar[0.95]*100:.2f}% | 99% {hvar[0.99]*100:.2f}%")
    print(f"Monte Carlo VaR: 95% {mcvar[0.95]*100:.2f}% | 99% {mcvar[0.99]*100:.2f}%")
    print(f"Max drawdown   : {portfolio_max_drawdown(returns, weights)*100:.2f}%")
    print(f"Portfolio beta : {portfolio_beta(returns, weights):.2f}")
    print("Asset betas    :", {t: round(asset_betas(returns)[t], 2) for t in TICKERS})

    print("\n--- Historical stress tests ---")
    for r in stress_test_all(returns, weights):
        if r.get("skipped"):
            print(f"  {r['label']:<28} [data not available] {r.get('note','')}")
            continue
        print(f"  {r['label']:<28} "
              f"projected DD {r['projected_drawdown']*100:6.2f}% | "
              f"window total {r['total_return']*100:6.2f}% | {r['n_obs']} obs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())