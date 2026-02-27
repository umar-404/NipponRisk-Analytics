# NipponRisk Analytics 🎌
![alt text](<NipponRisk Analytics.png>)

A lightweight portfolio **risk analytics & stress-testing** web application focused on the Japanese stock market. Given an allocation across four flagship Japanese names, it computes Value at Risk, maximum drawdown, beta, and simulates how that exact mix would have performed through two major historical shocks.

**Universe:** Toyota (`7203.T`) · Sony (`6758.T`) · Mitsubishi UFJ Financial Group (`8306.T`) · NTT (`9432.T`) · benchmark **Nikkei 225** (`^N225`)

**Stack:** Python (FastAPI · yfinance · pandas · numpy · scipy) backend + React · TypeScript · Tailwind CSS frontend.

---

## Features

| Module | What it does |
|--------|--------------|
| **Data pipeline** | Pulls ~7 years of daily **adjusted close** prices via `yfinance`, cleans/aligns all columns on common trading days, computes daily returns, and caches to parquet (no repeated network hits). |
| **Value at Risk** | `95%` and `99%`, 1-day horizon, via **both** Historical simulation and a seeded **Monte Carlo** (multivariate-Normal) engine. |
| **Maximum drawdown** | Rolling peak-to-trough drawdown time series plus the worst drawdown over the sample. |
| **Beta** | Per-asset beta vs the Nikkei 225, plus the weighted portfolio beta. |
| **Historical stress tests** | Runs your weights through **Aug 2024 Yen-Spike Crash** and **Mar 2020 COVID Shock**, reporting the exact **projected drawdown** and window total return. |
| **REST API** | `POST /api/analyze` returns every metric + full return/equity time series for charting; `GET /api/health` reports data freshness. |
| **Dashboard** | Responsive React + Tailwind UI with dynamic weight sliders, KPI stat cards for VaR/drawdown/beta, a Recharts line chart (portfolio vs benchmark with stress-window shading + focus-to-zoom), and a stress-test card grid. |

---

## Project Structure

```
NipponRisk Analytics/
├── README.md
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint (CORS, router, root route)
│   │   ├── config.py        # Ticker universe, stress windows, MC params, paths
│   │   ├── schemas.py       # Pydantic request/response models
│   │   ├── data/
│   │   │   ├── fetcher.py   # yfinance download + tidy long-form + retries
│   │   │   ├── cleaner.py   # artifact removal, alignment, daily returns
│   │   │   └── loader.py    # load cached aligned returns for the API
│   │   ├── risk/
│   │   │   ├── portfolio.py # weight validation/normalization, portfolio returns
│   │   │   ├── var.py       # Historical VaR
│   │   │   ├── monte_carlo.py # Monte Carlo VaR (multivariate Normal)
│   │   │   ├── drawdown.py  # max drawdown + series
│   │   │   ├── beta.py      # asset & portfolio beta vs ^N225
│   │   │   └── stress.py    # stress-window slicing + projected drawdowns
│   │   ├── api/router.py    # /api/analyze, /api/health
│   │   └── services/analysis.py # orchestration -> JSON-safe payload
│   ├── scripts/
│   │   ├── fetch_data.py    # fetch + clean + persist panels
│   │   ├── demo_analyze.py  # run a weighted analysis offline (CLI)
│   │   ├── demo_clean_pipeline.py
│   │   └── smoke_api.py     # exercise the API against real data
│   ├── tests/               # pytest (cleaner, fetcher, risk, api)
│   └── data/                # cached parquet panels (git-ignored)
└── frontend/                # React + TypeScript + Tailwind dashboard
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts       # /api proxy -> http://localhost:8000
    ├── tailwind.config.js
    ├── postcss.config.js
    └── src/
        ├── main.tsx / App.tsx / index.css / vite-env.d.ts
        ├── types.ts         # API contract types (mirror backend schemas)
        ├── lib/api.ts       # POST /api/analyze wrapper
        ├── lib/format.ts    # % / number formatting
        ├── components/      # WeightSliders, StatCard, PortfolioChart, StressGrid
        └── pages/Dashboard.tsx
```

---

## Requirements

> **No Docker / containers.** This project runs directly on your machine: python
> venv for the backend + node/npm for the frontend (two terminals). Docker is not
> used anywhere in the project.

- **Python 3.11+** (tested on 3.12)
- **Node.js 18+ / npm** (for the frontend)
- An internet connection (only for the initial `yfinance` fetch)

---

## Backend — Setup & Run

```bash
cd backend

# 1. Create + activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

### Fetch & clean the market data

```bash
python scripts/fetch_data.py                 # ~7y of daily adjusted closes -> data/returns.parquet
```

This writes:
- `data/returns.parquet` — aligned daily returns (consumed by the API)
- `data/prices.parquet` — aligned adjusted closes
- `data/raw_panel.parquet` — raw tidy frame (debug/cache)

### Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

- Interactive docs: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/api/health**

### Quick offline smoke test

```bash
python scripts/demo_analyze.py                # prints VaR, DD, beta, stress for equal weights
python scripts/demo_analyze.py --w 40 30 20 10   # custom weights (Toyota Sony MUFG NTT)
python scripts/smoke_api.py                   # exercises /, /api/health, /api/analyze
```

### Run the tests

```bash
python -m pytest tests/ -q         # 37 tests (cleaner, fetcher, risk, api)
```

---

## Frontend — Setup & Run

```bash
cd frontend
npm install        # installs React, TS, Tailwind, Recharts, Vite
```

### Run the dashboard (dev)

With the backend running on `:8000`, start Vite in a second terminal:

```bash
npm run dev        # http://localhost:5173  (proxies /api -> :8000)
```

### Build for production + typecheck

```bash
npm run typecheck  # tsc --noEmit
npm run build      # outputs to frontend/dist
```

To point the frontend at a non-default backend, set `VITE_API_BASE`, e.g.
`VITE_API_BASE=http://localhost:8000 npm run dev`.

### Run the whole app (quickest path — no Docker)

Open **two terminals** from the project root. No containers involved; each process
runs on your local Python/Node toolchain.

```bash
# Terminal 1 — backend (run from the backend/ directory)
cd backend
uvicorn app.main:app --reload --port 8000      # API at http://localhost:8000/docs

# Terminal 2 — frontend (run from the frontend/ directory)
cd frontend
npm run dev                                    # open http://localhost:5173
```

Vite proxies every `/api` request to the FastAPI backend on `:8000`, so the
dashboard works without any CORS configuration in dev.

---

## API Reference

### `POST /api/analyze`

Compute all risk metrics for a given allocation.

**Request body**

```json
{
  "weights": {
    "7203.T": 40,
    "6758.T": 30,
    "8306.T": 20,
    "9432.T": 10
  },
  "risk_free_rate": 0.0
}
```

Weights may be any scale (percent, fractions); they are normalized server-side. The benchmark `^N225` is **not** a weightable position — it is used as the beta and stress reference.

**Example with `curl`**

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"weights":{"7203.T":40,"6758.T":30,"8306.T":20,"9432.T":10}}'
```

**Response** (values are decimals; VaR / drawdowns reported as **positive losses**)

```json
{
  "tickers": ["7203.T", "6758.T", "8306.T", "9432.T"],
  "weights_norm": {"7203.T": 0.4, "6758.T": 0.3, "8306.T": 0.2, "9432.T": 0.1},
  "dates": ["2019-09-11", "...", "2026-09-09"],
  "portfolio_returns": [0.0012, -0.004, "..."],
  "benchmark_returns": [0.0009, "..."],
  "equity_curve": [100.0, 100.12, "..."],
  "benchmark_equity": [100.0, "..."],
  "var": {
    "historical":  {"p95": 0.020663, "p99": 0.035912},
    "monte_carlo": {"p95": 0.023643, "p99": 0.033357}
  },
  "max_drawdown": -0.264156,
  "asset_betas": {"7203.T": 0.844, "6758.T": 0.841, "8306.T": 0.774, "9432.T": 0.250},
  "portfolio_beta": 0.76979,
  "stress": [
    {"key": "yen-spike-2024", "label": "Aug 2024 Yen-Spike Crash",
     "start": "2024-07-01", "end": "2024-08-31",
     "projected_drawdown": 0.2479, "total_return": -0.0501, "n_obs": 43, "skipped": false},
    {"key": "covid-2020", "label": "March 2020 COVID Shock",
     "start": "2020-01-31", "end": "2020-04-30",
     "projected_drawdown": 0.2642, "total_return": -0.1257, "n_obs": 61, "skipped": false}
  ],
  "data_start": "2019-09-11T00:00:00",
  "data_end": "2026-09-09T00:00:00",
  "n_obs": 1707
}
```

| Field | Meaning |
|-------|---------|
| `equity_curve` / `benchmark_equity` | Cumulative portfolio / Nikkei growth, normalized to start at `100`. |
| `var.historical` / `var.monte_carlo` | 95% / 99% 1-day VaR as positive decimal daily losses. |
| `max_drawdown` | Worst peak-to-trough loss over the full sample (<= 0). |
| `asset_betas` / `portfolio_beta` | Sensitivity to the Nikkei 225. |
| `stress[].projected_drawdown` | How much this allocation would have **lost** during the window (positive loss); `None` + `skipped=true` if the data sample can't cover the window. |

### `GET /api/health`

```json
{
  "status": "ok",
  "n_obs": 1707,
  "data_start": "2019-09-11T00:00:00",
  "data_end": "2026-09-09T00:00:00",
  "cache_seconds": 86400
}
```

---

## Conventions & Methodology Notes

- **Returns** are simple daily returns (`P_t / P_{t-1} - 1`) stored as **decimals** internally.
- **Historical VaR** = 5th / 1st percentile of the weighted daily portfolio returns.
- **Monte Carlo VaR** = percentile of 10,000 multivariate-Normal scenarios fitted to the aligned asset returns (mean vector + covariance), projected through the weights. Seeded for reproducibility.
- **Stress projections** chain the weighted returns within each window and report the peak-to-trough drawdown of that exactly-weighted mix.
- **Lookback** is ~7 years by default so the data covers the earliest stress window (Mar 2020). Tune via `PERIOD` in `app/config.py`.


## Deployment (Vercel)

The project deploys to Vercel directly from GitHub. Vercel auto-detects and uses
the **FastAPI framework preset**: a root-level `main.py` re-exports the backend
`app` (so the risk math is identical to local dev), the React build is served as
static assets from `frontend/dist`, and `/api/*` requests run through the
FastAPI app.

Three files make this work:

- `main.py` (root) — FastAPI entrypoint that Vercel loads (`app` instance)
- `vercel.json` — build command + output directory (`frontend/dist`)
- `requirements.txt` (root) — runtime deps: fastapi, pandas, numpy, pyarrow

No environment variables are required. The frontend calls `/api/*` relative to
its own origin, so requests hit the same deployment.

**Local development is unchanged.** Deleting or abandoning the Vercel deployment
has no effect on running the project locally:

```bash
# Backend (terminal 1)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend && npm run dev
```

Vite's dev proxy forwards `/api/*` to `localhost:8000`, so the app works exactly
as it always has. The root `main.py` is only exercised by Vercel's build; local
runs never import it.

---

## License

Private / internal analytics tool by UMAR.