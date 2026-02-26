# NipponRisk Analytics

![Dashboard](NipponRisk%20Analytics.png)

Portfolio risk analytics & stress-testing for Japanese equities. Enter an allocation across Toyota (7203.T), Sony (6758.T), MUFG (8306.T), and NTT (9432.T) to compute VaR (historical + Monte Carlo), max drawdown, beta vs Nikkei 225, and projected performance through the Aug 2024 yen-spike and Mar 2020 COVID crashes.

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

## Features

- **VaR** — Historical (95%/99%) + Monte Carlo (10k scenarios, seeded)
- **Max Drawdown** — Rolling peak-to-trough + worst over sample
- **Beta** — Per-asset & portfolio vs Nikkei 225
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

Private / internal analytics tool.