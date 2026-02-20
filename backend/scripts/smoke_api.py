# NipponRisk Analytics
"""Smoke-test the FastAPI endpoints against the cached (real) data.

Usage:
    python scripts/smoke_api.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> int:
    client = TestClient(app)

    print("=== GET / ===")
    print(json.dumps(client.get("/").json(), indent=2))

    print("\n=== GET /api/health ===")
    h = client.get("/api/health")
    print(h.status_code, json.dumps(h.json(), indent=2))

    print("\n=== POST /api/analyze (equal weight) ===")
    r = client.post("/api/analyze", json={"weights": {"7203.T": 25, "6758.T": 25,
                                                      "8306.T": 25, "9432.T": 25}})
    body = r.json()
    print("status:", r.status_code)
    print("n_obs:", body.get("n_obs"), "| range:", body.get("data_start"), "->", body.get("data_end"))
    print("weights_norm:", body.get("weights_norm"))
    print("var:", body.get("var"))
    print("max_drawdown:", body.get("max_drawdown"))
    print("portfolio_beta:", body.get("portfolio_beta"))
    print("asset_betas:", body.get("asset_betas"))
    print("stress:")
    for s in body.get("stress", []):
        dd = f"{s['projected_drawdown']*100:.2f}%" if s.get("projected_drawdown") is not None else "n/a"
        tot = f"{s['total_return']*100:.2f}%" if s.get("total_return") is not None else "n/a"
        print(f"   {s['label']:<26} DD={dd}  total={tot}  skip={s.get('skipped')}")
    print("series lens:",
          len(body.get("dates", [])), len(body.get("portfolio_returns", [])),
          len(body.get("equity_curve", [])), len(body.get("benchmark_equity", [])))

    print("\n=== POST /api/analyze (unknown ticker -> expect 422) ===")
    r2 = client.post("/api/analyze", json={"weights": {"7203.T": 1.0, "AAPL": 1.0}})
    print("status:", r2.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())