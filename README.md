# NipponRisk Analytics

![Dashboard](NipponRisk%20Analytics.png)

Portfolio risk analytics and stress-testing for Japanese equities. Given an allocation across Toyota (`7203.T`), Sony (`6758.T`), MUFG (`8306.T`), and NTT (`9432.T`), the tool computes Value at Risk (historical and Monte Carlo), maximum drawdown, beta versus the Nikkei 225, and replays the portfolio through the Aug 2024 yen-spike and Mar 2020 COVID shocks.

## Quick Start

```bash
# Terminal 1 — Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_data.py
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install && npm run dev
```

Open http://localhost:5173

## Conventions & Methodology

- **Returns** are simple daily returns (`P_t / P_{t-1} - 1`), stored as decimals.
- **Historical VaR** is the 5th/1st percentile of the weighted daily portfolio returns.
- **Monte Carlo VaR** is the percentile of 10,000 multivariate-Normal scenarios fitted to the aligned asset returns (mean vector + covariance) and projected through the weights; seeded for reproducibility.
- **Stress projections** chain the weighted returns within each window and report the peak-to-trough drawdown of that exact mix.
- **Lookback** is ~7 years by default so the sample covers the earliest stress window (Mar 2020). Tune via `PERIOD` in `app/config.py`.

## Features

- **VaR** — Historical (95%/99%) + Monte Carlo (10,000 scenarios, seeded)
- **Max Drawdown** — Rolling peak-to-trough + worst over sample
- **Beta** — Per-asset and portfolio vs Nikkei 225
- **Stress Tests** — Aug 2024 yen-spike, Mar 2020 COVID shock
- **Dashboard** — Weight sliders, KPI cards, Recharts equity curve with stress-window shading

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12, FastAPI, yfinance, pandas, numpy, scipy, pytest |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |

## Tests

```bash
cd backend && python -m pytest -q      # 37 tests
cd frontend && npm run typecheck && npm run build
```

---

Private / internal analytics tool by Umar.