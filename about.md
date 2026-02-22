# NipponRisk Analytics — Complete Project Walkthrough

A deep-dive explanation of the **NipponRisk Analytics** application from both a
**computer-science / software standpoint** and a **quantitative-finance
standpoint**. By the end of this document you should be able to explain to anyone
*what the app is*, *what every file does*, *which features it uses*, and *how each
one is implemented under the hood* — including the actual math.

---

## 1. What is NipponRisk Analytics?

NipponRisk Analytics is a **web application** that lets a user enter a portfolio
allocation across four major Japanese stocks and immediately see how risky that
portfolio is. It answers questions a trader or quantitative analyst would ask:

- *"What is the maximum I could reasonably lose in a single day?"* → **Value at Risk (VaR)**.
- *"How far could this portfolio fall from its peak?"* → **Maximum Drawdown**.
- *"How sensitive is this portfolio (and each stock) to the overall Japanese market?"* → **Beta**.
- *"What would have happened to *this exact mix* during the August 2024 yen-spike crash and the March 2020 COVID crash?"* → **Historical Stress Testing**.

It is deliberately **lightweight** — no database, no message queue, no Docker. It
is built from two small halves that talk to each other over HTTP:

| Half | Tech | Role |
|------|------|------|
| **Backend** | Python · FastAPI · yfinance · pandas · numpy · scipy | Fetch & clean market data, run the risk math, expose a REST API |
| **Frontend** | React · TypeScript · Tailwind CSS · Recharts · Vite | Interactive dashboard: sliders, stat cards, charts |

**The asset universe (from a finance sense):**
- **7203.T** — Toyota (auto manufacturing)
- **6758.T** — Sony Group (electronics / entertainment)
- **8306.T** — Mitsubishi UFJ Financial Group (banking / financials)
- **9432.T** — NTT (telecom)
- **^N225** — the **Nikkei 225** index, used as the market benchmark

These were chosen because they are four of the most liquid, widely-held Japanese
names and span very different sectors (industrials, consumer tech, financials,
telecom), so they respond differently to market shocks.

---

## 2. High-Level Architecture & Request Flow

```
   React Dashboard (frontend, :5173)
        │  fetch("POST /api/analyze", { weights })
        │        ▼
   Vite dev-server proxy (/api → localhost:8000)
        │        ▼
   FastAPI app (backend, :8000)
   app/api/router.py ──► app/services/analysis.py ──► app/risk/*.py
        │                        │                       (VaR, MC, drawdown, beta, stress)
        │                        └── reads cached panel ──► app/data/loader.py
        ▼
   JSON response (VaR, drawdown, beta, stress, time series)
```

1. The React dashboard collects **weights** from sliders/inputs.
2. It calls the backend endpoint (in dev, Vite proxies `/api` to FastAPI so there
   are **no CORS issues**).
3. FastAPI validates the request, normalizes weights, loads the cached returns
   panel, runs the five risk modules, and returns a JSON payload.
4. React renders the numbers as **stat cards** and the time series as a **chart**.

Because the market data is **pre-computed and cached to parquet**, every analysis
request is just in-memory math — it returns in milliseconds.

---

## 3. The Backend — Every File, Explained

### 3.1 `backend/requirements.txt`
The dependency manifest. Because the frontend and backend are two separate
processes, the backend has its own Python requirements:
- `fastapi` + `uvicorn[standard]` — the web server and ASGI app framework.
- `pydantic` — data validation for request/response.
- `yfinance` — free market-data downloader (Yahoo Finance).
- `pandas`, `numpy`, `scipy` — data frames, linear algebra, statistics.
- `pyarrow` — parquet format for fast disk caching.
- `pytest` + `httpx` — testing.

### 3.2 `backend/app/config.py` — the single source of truth
This is the "brain of the project settings." It declares:
- **`TICKERS`** — the four tradable stock symbols.
- **`BENCHMARK`** — `^N225` (used only as the market reference, never weightable).
- **`TICKER_NAMES`** — display names for the UI.
- **`ALL_SYMBOLS`** — assets + benchmark.
- **`PERIOD = "7y"`** — how much history to fetch. *(Why 7 years and not 5? So the
  data still reaches back before the **March 2020** COVID window. A naive 5y
  window from today would start *after* March 2020.)*
- **`CACHE_MAX_AGE_SECONDS`** — how stale the cached data may be (24h default).
- **`StressWindow`** dataclass + **`STRESS_WINDOWS`** — the two shock windows as
  date ranges, with a human-readable `event` description.
- **`MonteCarloParams`** — how many scenarios, which confidence levels, and the
  random seed used by the Monte Carlo engine.

### 3.3 `backend/app/data/fetcher.py` — pulling data from the real world
This module talks to **Yahoo Finance via `yfinance`**:
- `download_adj_close_prices()` calls `yf.download(...)` with:
  - `period="7y"`, `interval="1d"` → 7 years of daily bars,
  - `auto_adjust=True` → request **adjusted close** (prices that already account
    for stock **splits** and **dividends**, so return math isn't distorted by
    corporate actions),
  - `group_by="ticker"` → yfinance returns a DataFrame with a two-level
    (MultiIndex) column: `(TICKER, 'Open' | 'High' | ... )`.
- `_download_with_retries()` wraps the call with **3 attempts and linear
  backoff** (5s, then 10s) — network calls to Yahoo frequently fail transiently,
  so the app politely retries instead of crashing.
- `_melt_closes()` handles a real-world quirk: **newer yfinance folds adjustment
  into a `Close` column and drops the separate `Adj Close` column**. The code
  checks which price field exists (`Adj Close` if present, otherwise `Close`) and
  reshapes ("melts") the wide frame into **tidy/long format**:
  `[date, ticker, adj_close]` — one row per (day, asset).
- `save_raw_cache()` / `load_cached_raw()` persist/read this raw frame as a
  **parquet** file so repeated dev runs don't re-download.

### 3.4 `backend/app/data/cleaner.py` — cleaning & feature engineering
Market data is messy; this module turns raw prices into a clean, analysis-ready
panel:
1. **`build_panel()`** pivots the long frame into a **wide** `date × symbol`
   matrix of adjusted closes. It **drops zero/negative prices** (impossible in
   reality — a data artifact) and normalizes dates to tz-naive midnights.
2. **`drop_non_trading_rows()`** performs an **inner join on dates**: it removes
   any day on which not every asset + benchmark has a value. This guarantees all
   columns are **contemporaneous**, a hard requirement for covariance/beta math.
3. **`compute_returns()`** computes **simple daily returns**:
   `r_t = (P_t / P_{t-1}) − 1`. It uses `diff() / shift(1)` (not `pct_change`)
   to stay compatible across pandas versions, converts infinities to NaN, and
   drops the first row (which has no prior price).
4. **`build_clean_dataset()`** chains all of that and returns both the aligned
   price panel and the aligned returns panel. It also *warns* (rather than
   crashes) if fewer than the expected minimum trading days are present.

### 3.5 `backend/app/data/loader.py` — the API's data doorway
A tiny but important module: `load_returns_panel()` reads the **cached
`returns.parquet`** back into a pandas DataFrame and normalizes its index to
tz-naive dates (so date comparisons in the risk engine always work, regardless of
how the file was originally saved). It raises a clear `FileNotFoundError` if you
haven't run the fetch script yet.

> **Why parquet caching?** The frontend may fire dozens of analysis requests in a
> second (while dragging a slider). Re-downloading from Yahoo on every one would
> be slow, rate-limited, and fragile. By precomputing **once** and loading from
> disk, each API call is a pure in-memory computation.

### 3.6 `backend/app/risk/portfolio.py` — building the portfolio series
The bridge between "weights" and "risk math". `portfolio_returns(weights, panel)`
turns the wide returns panel plus a weight vector into **one weighted portfolio
return series** — a matrix–vector product `R · w` (pandas dot), honoring the
*fixed-weight, daily-rebalanced-equivalent* convention (each day's return is
the weighted sum of that day's asset returns, which is equivalent to
rebalancing to target weights daily). It also provides:
- **`normalize_weights()`** — accepts any positive weights summing to anything
  and rescales them to sum to 1 (`w / Σw`), so the UI can accept raw
  slider values like `50/50/50/50`.
- **`equity_index()`** — compounds the return series into an **equity curve
  starting at 100**: `100 · Π(1 + rₜ)`. Compounding (geometric linking) is
  what makes multi-period performance comparable — arithmetic summation would
  misrepresent growth over 1700 days.

### 3.7 `backend/app/risk/var.py` — Historical Value at Risk
**The finance idea:** "VaR at 95% means that, under normal historical conditions,
there is only a 5% chance the portfolio loses more than X% in a single day." This
implementation uses a **historical-simulation** method — it makes **no
distributional assumptions** and simply looks at the actual observed returns of
your weighted portfolio.

**The implementation:**
1. Build the portfolio's daily returns (weighted dot product).
2. Drop any non-finite values.
3. For each confidence level `cl`, take the **quantile** of the return
   distribution at percentile `(1 − cl) × 100` (e.g. 5th percentile for 95%).
4. Because returns are mostly negative in the tail, it returns **`-q`**, i.e. the
   loss expressed as a **positive number** (so "0.023" = a 2.3% expected loss).

### 3.8 `backend/app/risk/monte_carlo.py` — Monte Carlo VaR
**The finance idea:** rather than only reusing observed history, *simulate* tens
of thousands of possible tomorrows under a statistical model, and measure the
loss distribution of those simulated days.

**The implementation:**
1. **`estimate_moments()`** fits a **mean vector `μ`** and a **covariance matrix
   `Σ`** to the aligned asset returns (`np.cov`, sample ddof=1). The covariance
   matrix captures how the four stocks *co-move* (e.g. financials and industrials
   both falling when the market falls).
2. **Draw scenarios** from a **multivariate Normal** distribution
   `𝒩(μ, Σ)` — `np.random.multivariate_normal`. `MonteCarloParams` sets
   10,000 scenarios and a **fixed seed (42)** so results are **reproducible**.
3. Project each simulated scenario to a portfolio return with the dot product
   `scenario @ w`.
4. Take the tail quantiles (5th / 1st percentile) → VaR, again returned as a
   positive loss.

> *Why both methods?* Historical VaR is robust and assumption-free but is limited
> to what actually happened. Monte Carlo VaR can explore a smooth model of
> co-movement but assumes **normality** (it can underestimate extreme-tail risk
> for equities, which are "fat-tailed"). Showing both side by side gives the user
> two lenses on the same risk.

### 3.9 `backend/app/risk/drawdown.py` — Maximum Drawdown
**The finance idea:** drawdown is the percentage an investment has fallen from
its **previous all-time high**. "Maximum drawdown" is the worst such fall in the
sample — the deepest peak-to-trough loss you would have experienced.

**The implementation:**
- `drawdown_series()` computes an equity curve, then a **running peak** via
  `cummax()`, and `dd = equity / running_peak − 1`. Because the running peak is
  always ≥ the current equity, drawdown is **≤ 0**. It's clipped at 0 to avoid
  float noise.
- `max_drawdown()` returns `dd.min()` — the most negative value (the worst
  trough). The UI flips this sign to show a positive "loss from peak."

### 3.10 `backend/app/risk/beta.py` — Beta vs the Nikkei 225
**The finance idea:** Beta measures an asset's systematic risk — how strongly it
moves with the market. `β = 1.0` means it moves with the market on average; `β >
1` amplifies market moves (high-flyer); `β < 1` dampens them (defensive).

**The implementation:**
- `asset_betas()` computes, for each stock, the **slope of its returns versus the
  benchmark**: `β = Cov(r_asset, r_bench) / Var(r_bench)`, using
  `np.cov(...)` with ddof=1. It guards against a zero-variance benchmark.
- `portfolio_beta()` returns the **weighted average** of the per-asset betas:
  `β_p = Σ wᵢ · βᵢ`. This is correct because portfolio return is a linear
  weighted sum of asset returns.

### 3.11 `backend/app/risk/stress.py` — Historical Stress Testing
**The finance idea:** past is prologue. Instead of assuming tomorrow looks like a
"normal" day, *stress testing* replays exact crisis windows and asks, *"how would
my current allocation have done?"*

**The implementation:**
- `slice_window()` selects all aligned-return rows whose **dates fall inside a
  window** (inclusive), handling naive vs aware timezones.
- `stress_test_window()` builds the **weighted portfolio returns** over just that
  window, computes the **max drawdown** of those returns, and chains the
  compounding to get the **window total return** `Π(1+r) − 1`.
- `stress_test_all()` runs every configured window and is **defensive**: if a
  window falls entirely outside the fetched data range it returns a
  `skipped=True` entry (with a note) instead of raising, so the API never
  500-errors on a short sample.

### 3.12 `backend/app/services/analysis.py` — the orchestration layer
`run_analysis(weights)` is the glue:
1. Loads the aligned returns panel (or accepts an injected one, for tests).
2. Normalizes the weights.
3. Builds portfolio returns/equity and benchmark equity (both indexed to 100).
4. Computes historical VaR, Monte Carlo VaR, max drawdown, asset/portfolio beta,
   and all stress windows.
5. Returns a **JSON-serializable** plain dict — every numpy scalar and
   `pd.Timestamp` is cast to native Python (`round(float(...))`, `isoformat()`),
   because FastAPI/JSON cannot natively serialize numpy types.

`health_payload()` summarizes sample size/range for the health endpoint.

### 3.13 `backend/app/schemas.py` — the API contract (Pydantic)
Defines **the shape of data crossing the network boundary** using Pydantic.
Pydantic is FastAPI's validation engine: it checks types, rejects invalid
input with a helpful `422` error, and generates the OpenAPI docs at `/docs`.

- **`Weights`** — a dict mapping each of the four ticker strings to a float.
  Validation guarantees the user cannot send `"AAPL": 50` or a negative weight.
- **`PortfolioInput`** — the request body: `{ "weights": {...} }`.
- **`VaRResult` / `VarBlock`** — VaR numbers at the 95%/99% levels for both the
  historical and Monte Carlo methods (`var.historical.p95`, etc.).
- **`StressResult`** — one stress window's outcome: `key`, `label`, `start/end`,
  `obs` (trading days in window), `portfolio_drawdown` (peak-to-trough %),
  `window_return`, and `skipped` + `note` when the window lies outside the
  data range.
- **`AnalysisResult`** — the full response: normalized weights, VaR blocks,
  max drawdown, per-asset betas, portfolio beta, `dates`, `equity_curve`,
  `benchmark_equity`, and the stress list.
- **`HealthResponse`** — sample size, date range, tickers, for `GET /api/health`.

The schema is the *single source of truth* — kept deliberately in sync with
the frontend's `types.ts`.

### 3.14 `backend/app/api/router.py` — the HTTP endpoints
Two routes, deliberately minimal:

- **`POST /api/analyze`** — the core endpoint. Flow:
  1. FastAPI/Pydantic validates the body against `PortfolioInput`.
  2. `loader.load_returns()` runs; if the parquet cache is missing it returns
     **HTTP 503** with *"run the fetch script first"* — a friendly operational
     error, not a stack trace.
  3. `run_analysis(weights)` executes the risk engine.
  4. Any unexpected exception is caught and re-raised as **HTTP 400** with the
     message, so the client always gets structured JSON, never a raw 500.
- **`GET /api/health`** — a readiness probe returning the sample size and date
  range of the cached panel (or `503` if the cache is missing); the dashboard
  uses it to display "data through 2026-09-09".

### 3.15 `backend/app/main.py` — the application entrypoint
Creates the FastAPI instance and wires everything together:
- `include_router(router)` mounts the `/api` routes.
- **CORSMiddleware** allows the Vite dev origin (`http://localhost:5173`).
  Redundant in dev (Vite proxies `/api`), but it makes the API usable from
  curl, Postman, or any other local client without surprises.
- A root `/` route with a tiny JSON description, plus the automatic
  interactive docs at `/docs` (Swagger UI).

### 3.16 `backend/tests/` — the test suite (37 tests)
Split by layer and run on **synthetic data**, so they are offline and fast:

| File | What it covers |
|---|---|
| `test_cleaner.py` | panel alignment, zero/negative-price cleaning, return computation, timezone normalization |
| `test_fetcher.py` | reshaping for *both* yfinance column layouts (`Close` only and `Adj Close` present), tidy-frame structure |
| `test_risk.py` | portfolio math, historical & Monte Carlo VaR against hand-computed values, drawdown on known curves, **exact beta** on constructed data, stress slicing |
| `test_api.py` | the HTTP contract via FastAPI's `TestClient` with an *injected* synthetic panel — no network, no cache: 200 on valid weights plus 400/503/422 error paths |

Because `run_analysis()` accepts an injected returns panel, the API tests are
deterministic and hermetic — dependency injection making code testable.

### 3.17 `backend/scripts/` — operational entrypoints
- **`fetch_data.py`** — the one-time (and refresh) script: downloads 7 years of
  data, cleans it, writes the parquet cache the API serves from.
- **`demo_clean_pipeline.py`** — runs the whole pipeline on **synthetic**
  prices to verify plumbing without touching the network.
- **`demo_analyze.py`** — runs the risk engine offline on the cached panel and
  pretty-prints the same payload the API returns.
- **`smoke_api.py`** — boots the analysis service in-process and calls every
  endpoint, verifying the full stack end-to-end.

---

## 4. The Frontend — Every File, Explained

A **Vite + React 18 + TypeScript** single-page app styled with **Tailwind CSS**
and charted with **Recharts**. It is a *thin client*: all math lives on the
server; the frontend collects weights, renders results, and handles
loading/error states.

### 4.1 Build & config files
- **`package.json`** — deps (`react`, `react-dom`, `recharts`), dev tooling
  (`vite`, `typescript`, `tailwindcss`, `@vitejs/plugin-react`). Scripts:
  `dev`, `build` (type-check + bundle), `typecheck` (`tsc --noEmit`).
- **`vite.config.ts`** — the key line is the **dev proxy**: `/api/*` is
  forwarded to `http://localhost:8000`. That's why the frontend can call
  `fetch("/api/analyze")` with no CORS config and works identically in dev
  and production.
- **`tsconfig.json`** — strict TypeScript (strict null checks, etc.) so type
  errors are caught at compile time, not at runtime in the browser.
- **`tailwind.config.js` / `postcss.config.js`** — register Tailwind's utility
  classes with PostCSS; Tailwind scans `src/**` for class names.
- **`index.html`** — the single HTML shell; Vite injects the React bundle.
- **`src/index.css`** — Tailwind directives (`@tailwind base/components/utilities`).
- **`src/main.tsx` / `src/App.tsx` / `src/vite-env.d.ts`** — React bootstrap:
  mount `<App/>` into `#root`; `App` renders the Dashboard page; the `.d.ts`
  teaches TypeScript about Vite's `import.meta.env`.

### 4.2 `src/types.ts` — the mirrored API contract
Hand-written TypeScript interfaces **mirroring the Pydantic schemas**:
`Weights`, `VarBlock`, `VaRResult`, `StressResult`, `AnalysisResult`, plus
constants `TICKERS` and `TICKER_NAMES`. Because the backend guarantees the
shape, the frontend consumes responses with full type safety and zero runtime
validation.

### 4.3 `src/lib/api.ts` — the network layer
A tiny typed wrapper over `fetch`:
- `analyze(weights)` — `POST /api/analyze`; on non-OK responses it extracts
  FastAPI's `detail` field and throws a readable `Error` (so the UI can show
  *"cache missing — run fetch script"* instead of "HTTP 503").
- `fetchHealth()` — calls `/api/health`.
- Base URL defaults to `""` (same origin, proxied); override with the
  `VITE_API_BASE` env var for a split deployment.

### 4.4 `src/lib/format.ts` — display formatting
Pure helpers so every number renders consistently: `pctLoss` (losses like
`-1.79%` with fixed decimals), `fmt` (thousands separators), and short date
labels for chart axes.

### 4.5 `src/components/WeightSliders.tsx` — the input UI
For each asset, a **range slider and a number input bound to the same state**
(move either one). Below them, a live **normalization meter**: shows the raw
sum and warns in amber when it isn't 100%. The backend normalizes
proportionally anyway, so the meter is honest UX: `50+50+50+50` is treated as
`25/25/25/25`.

### 4.6 `src/components/StatCard.tsx` — the KPI tiles
A reusable card (label, value, sub-label, optional accent color) used for the
six headline metrics: Historical VaR 95/99, Monte Carlo VaR 95/99, Max
Drawdown, Portfolio Beta. Generic by design — adding a metric later is a
one-line change.

### 4.7 `src/components/PortfolioChart.tsx` — the performance chart
A Recharts `LineChart` with two series: the **portfolio equity curve** and the
**Nikkei 225**, both indexed to 100 at the start so their shapes are directly
comparable regardless of actual price levels. Implementation details:
- **`downsample()`** — thins the ~1700-day series to ≤600 points (uniform
  stride) so the SVG stays snappy; visually indistinguishable.
- **`ReferenceArea`** shades each historical **stress window**, so you can
  literally see the Aug-2024 and Mar-2020 crashes on the curve.
- **`focusWindowKey`** — clicking a stress card zooms the x-axis to that
  window's date range.

### 4.8 `src/components/StressGrid.tsx` — the crisis report
One card per stress window: projected **portfolio drawdown**, **window total
return**, trading-day count, and a one-line event description ("BoJ rate
hike / yen-carry unwind", "COVID-19 global selloff"). Clicking a card focuses
the chart. Skipped windows render muted/disabled with the note.

### 4.9 `src/pages/Dashboard.tsx` — the page that ties it together
The single page, and the most instructive file for React patterns:
- **State:** `weights`, `result`, `loading`, `error`, `focusWindowKey`.
- **Debounced live recompute:** a `useEffect` on `weights` waits **350 ms**
  after the last change before calling the API — dragging a slider doesn't
  fire a request per pixel.
- **Race-condition guard:** a `requestSeq` counter ensures that if two
  requests are in flight, **only the latest response** updates state; stale
  responses are discarded.
- **Optimistic defaults:** while the first request loads, equal-weight
  placeholders render so the layout never jumps.
- **Layout:** header → sliders + stat cards → chart → stress grid → asset-beta
  table, all responsive via Tailwind grid classes.

---

## 5. The API Reference

### `POST /api/analyze`
Request:
```json
{ "weights": { "7203.T": 0.4, "6758.T": 0.3, "8306.T": 0.2, "9432.T": 0.1 } }
```
(Weights need not sum to 1 — they are normalized server-side.)

Response (abridged):
```json
{
  "weights_norm": { "7203.T": 0.4, "...": 0.1 },
  "var": {
    "historical":  { "p95": 0.0179, "p99": 0.0320 },
    "monte_carlo": { "p95": 0.0209, "p99": 0.0299 }
  },
  "max_drawdown": -0.2642,
  "beta": { "portfolio": 0.77, "assets": { "7203.T": 0.84, "...": 0.25 } },
  "dates": ["2021-09-01", "..."],
  "equity_curve":     [100.0, "..."],
  "benchmark_equity": [100.0, "..."],
  "stress": [
    { "key": "yen_spike_2024", "label": "August 2024 Yen-Spike Crash",
      "portfolio_drawdown": -0.2479, "obs": 43, "skipped": false }
  ]
}
```
Errors: `422` invalid weights · `503` cache missing (run `fetch_data.py`) ·
`400` unexpected analysis failure.

### `GET /api/health`
Returns the cached panel's sample size and date range, or `503` if absent.

Interactive docs are auto-generated at **`/docs`** (Swagger UI).

---

## 6. How to Run the Project (no Docker — two terminals)

```bash
# --- Backend (terminal 1) ---------------------------------------------
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_data.py        # once: download & cache 7y of data
uvicorn app.main:app --reload --port 8000
#   → API at http://localhost:8000, docs at http://localhost:8000/docs

# --- Frontend (terminal 2) --------------------------------------------
cd frontend
npm install
npm run dev
#   → Dashboard at http://localhost:5173  (proxies /api → :8000)
```

Verification: `cd backend && pytest -q` (37 tests) and
`cd frontend && npm run typecheck && npm run build`.

---

## 7. Conventions, Assumptions & Limitations

- **Sign convention:** VaR and drawdowns are reported as *positive loss
  magnitudes* in the risk modules and rendered with a minus sign in the UI.
- **Adjusted closes:** yfinance with `auto_adjust=True` folds dividends/splits
  into `Close` (there is no separate `Adj Close` in current yfinance) — the
  fetcher supports both layouts.
- **Sample window:** 7 years by default — chosen so the March 2020 window is
  inside the sample (5 years would exclude it).
- **Fixed-weight trading assumption:** no rebalancing — portfolio returns are
  the daily weighted sum of asset returns.
- **Monte Carlo assumes multivariate normality** with a seeded RNG for
  reproducibility; fat tails (Student-t) would be the natural extension.
- **No persistence of user portfolios** — state lives in the browser only.
- **Not investment advice** — an educational analytics tool.

---

## 8. Explaining the Project in 60 Seconds (elevator pitch)

> "NipponRisk Analytics is a full-stack portfolio risk dashboard for Japanese
> equities. A FastAPI backend pulls seven years of prices for Toyota, Sony,
> MUFG, and NTT via yfinance, aligns them with the Nikkei 225, and caches the
> cleaned daily-return panel as parquet. On each request it computes
> historical and Monte Carlo Value at Risk at 95/99%, maximum drawdown, and
> betas versus the Nikkei, then replays the user's exact allocation through
> the August 2024 yen-carry-unwind crash and the March 2020 COVID crash to
> project crisis drawdowns. A React + TypeScript + Tailwind dashboard with
> Recharts lets you move weight sliders and see every metric and the
> portfolio-vs-benchmark curve update live, with stress windows shaded on the
> chart. The backend is fully unit-tested (37 tests) and the whole stack runs
> locally with two commands — no database, no containers."

**Likely follow-up questions & answers:**
- *"Why two VaR methods?"* — Historical is non-parametric (no distribution
  assumption but limited by observed data); Monte Carlo is parametric
  (smooth, unlimited scenarios, but assumes normality). Agreement between
  them is a sanity check; divergence signals tail risk beyond normality.
- *"Why beta vs the Nikkei?"* — it decomposes risk into market-driven
  (systematic) vs idiosyncratic; NTT's low beta (~0.25) is why a heavy NTT
  allocation lowers portfolio beta.
- *"What's the hardest engineering part?"* — data alignment (timezones,
  Japanese holiday calendar, per-ticker gaps) and keeping the API contract
  type-safe across two languages (Pydantic ↔ TypeScript).
- *"How would you scale it?"* — scheduled refetch with cache TTL, larger
  universes, portfolio persistence, and a Student-t or EVT-based tail model.