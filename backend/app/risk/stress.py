# NipponRisk Analytics
"""Historical stress-testing: run weights through defined crisis windows.

Each window slices the aligned returns panel by date, builds weighted portfolio
returns over that window, and computes the projected maximum drawdown and the
window's total (compounded) return — i.e. how this exact asset mix would have
fared during that historical shock.
"""

from __future__ import annotations

import pandas as pd

from app.config import STRESS_WINDOWS, StressWindow
from app.risk.drawdown import max_drawdown
from app.risk.portfolio import portfolio_returns


def slice_window(returns: pd.DataFrame, window: StressWindow) -> pd.DataFrame:
    """Return the aligned returns rows within a window (inclusive).

    Works whether the index is tz-naive or tz-aware (matches naive window bounds).
    """
    idx = returns.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    start = pd.Timestamp(window.start)
    end = pd.Timestamp(window.end)
    mask = (idx >= start) & (idx <= end)
    return returns.loc[mask]


def stress_test_window(
    returns: pd.DataFrame, weights: dict[str, float], window: StressWindow
) -> dict:
    """Project the given weights through a single stress window.

    Returns
    -------
    dict
        ``{key, label, start, end, event, projected_drawdown, total_return,
           n_obs}`` where projected_drawdown and total_return are **positive
        drawdown and signed total return** figures (as decimals).
    """
    wslice = slice_window(returns, window)
    if wslice.empty:
        raise ValueError(f"Stress window {window.key} has no rows in the data sample.")

    pr = portfolio_returns(wslice, weights).dropna()
    if pr.empty:
        raise ValueError(f"Stress window {window.key} produced no portfolio returns.")

    dd = max_drawdown(pr)
    total_return = float((1.0 + pr).prod() - 1.0)

    return {
        "key": window.key,
        "label": window.label,
        "start": window.start,
        "end": window.end,
        "event": window.event,
        "projected_drawdown": float(-dd),  # positive loss figure
        "total_return": total_return,
        "n_obs": int(len(pr)),
    }


def stress_test_all(
    returns: pd.DataFrame,
    weights: dict[str, float],
    windows: tuple[StressWindow, ...] = STRESS_WINDOWS,
) -> list[dict]:
    """Run weights through every configured stress window.

    Windows that fall entirely outside the fetched data range are reported with
    ``skipped=True`` (and a note) instead of raising, so the API never 500s.
    """
    results: list[dict] = []
    lo, hi = returns.index.min(), returns.index.max()
    for w in windows:
        start, end = pd.Timestamp(w.start), pd.Timestamp(w.end)
        if end < lo or start > hi:
            results.append({**w.__dict__, "projected_drawdown": None,
                            "total_return": None, "n_obs": 0,
                            "skipped": True,
                            "note": f"Data sample {lo.date()}..{hi.date()} does not cover this window."})
            continue
        r = stress_test_window(returns, weights, w)
        r["skipped"] = False
        r.setdefault("note", "")
        results.append(r)
    return results