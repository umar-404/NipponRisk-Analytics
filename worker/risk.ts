// NipponRisk Analytics
// Cloudflare Worker risk engine: a TypeScript port of the Python backend
// (backend/app/risk/* + services/analysis.py). It computes VaR (historical +
// Monte Carlo), max drawdown, betas and stress-test projections from the bundled
// aligned-returns panel in worker/data/returns.ts.
//
// Numeric conventions match the Python reference:
//   - Simple daily returns stored as decimals.
//   - Historical VaR = linear-interpolation percentile of the weighted daily
//     portfolio returns, reported as a positive daily loss.
//   - Monte Carlo VaR = percentile of 10,000 seeded multivariate-Normal
//     1-day scenarios projected through the portfolio weights.
//   - Beta = Cov(asset, benchmark) / Var(benchmark) (ddof=1).
//   - Drawdown is peak-to-trough equity / running peak - 1, clipped at 0.
//   - Stress windows slice the panel by inclusive ISO dates.

import {
  BENCHMARK,
  CACHE_MAX_AGE_SECONDS,
  MONTE_CARLO,
  STRESS_WINDOWS,
  TICKERS,
  type StressWindow,
} from "./config";
import { COLUMNS, DATES, RETURNS } from "./data/returns";

// --------------------------------------------------------------------------- //
// Data access
// --------------------------------------------------------------------------- //

const ROW_COUNT = RETURNS.length;
const COL_COUNT = COLUMNS.length;

let COLUMN_MAJOR: Record<string, number[]> | null = null;

/** Panel exposed as column-major arrays: column name -> returns per day. */
function panel(): Record<string, number[]> {
  if (COLUMN_MAJOR) return COLUMN_MAJOR;
  const p: Record<string, number[]> = {};
  for (let c = 0; c < COL_COUNT; c++) {
    const col = new Array<number>(ROW_COUNT);
    for (let r = 0; r < ROW_COUNT; r++) col[r] = RETURNS[r][c] as number;
    p[COLUMNS[c] as string] = col;
  }
  COLUMN_MAJOR = p;
  return p;
}

/** Module-level ISO date strings (same order as panel rows). */
function dates(): string[] {
  return DATES as string[];
}

// --------------------------------------------------------------------------- //
// Small numeric helpers
// --------------------------------------------------------------------------- //

const finite = (v: number): boolean => Number.isFinite(v);

/** Python-like round(x, nd): round to nd decimals (uses toFixed round-half-up). */
export function roundDec(v: number, nd: number): number {
  return Number(v.toFixed(nd));
}

function mean(a: number[]): number {
  let s = 0;
  for (const x of a) s += x;
  return s / a.length;
}

/** Sample variance / covariance with ddof degrees-of-freedom correction. */
function variance(a: number[], ddof: number): number {
  const m = mean(a);
  let s = 0;
  for (const x of a) s += (x - m) * (x - m);
  return s / (a.length - ddof);
}

function covariance(a: number[], b: number[], ddof: number): number {
  const ma = mean(a);
  const mb = mean(b);
  let s = 0;
  for (let i = 0; i < a.length; i++) s += (a[i] - ma) * (b[i] - mb);
  return s / (a.length - ddof);
}

/**
 * numpy percentile with the default "linear" interpolation over sorted values.
 * `p` is in percent (e.g. 5 -> the 5th percentile).
 */
function percentile(sorted: number[], p: number): number {
  const n = sorted.length;
  if (n === 0) return Number.NaN;
  if (n === 1) return sorted[0];
  const rank = (p / 100) * (n - 1);
  const lo = Math.floor(rank);
  const hi = Math.ceil(rank);
  if (lo === hi) return sorted[lo];
  const frac = rank - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
}

// --------------------------------------------------------------------------- //
// Weights & portfolio math
// --------------------------------------------------------------------------- //

/**
 * Validate & normalize a weight map over the tradable universe.
 * Drops unknown tickers, clips negatives to 0, re-normalizes to sum 1, and
 * falls back to equal weights when nothing usable is provided.
 */
export function normalizeWeights(weights: Record<string, number>): number[] {
  const vec = TICKERS.map((t) => {
    const raw = weights?.[t];
    return typeof raw === "number" && finite(raw) ? Math.max(raw, 0) : 0;
  });
  const total = vec.reduce((a, b) => a + b, 0);
  if (total <= 1e-9) return TICKERS.map(() => 1 / TICKERS.length);
  return vec.map((w) => w / total);
}

/** Weighted daily portfolio returns over the given rows (NaN row weights -> NaN). */
function portfolioReturns(
  p: Record<string, number[]>,
  w: number[],
  rows: number[],
): number[] {
  const assetCols = TICKERS.map((t) => p[t]);
  return rows.map((r) => {
    let sum = 0;
    for (let c = 0; c < assetCols.length; c++) sum += (assetCols[c] as number[])[r] * w[c];
    return sum;
  });
}

/** Compound simple returns into an equity curve normalized to `start`. */
function cumulativeEquity(returns: number[], start = 100): number[] {
  const out = new Array<number>(returns.length);
  let eq = start;
  for (let i = 0; i < returns.length; i++) {
    eq *= 1 + returns[i];
    out[i] = eq;
  }
  return out;
}

function range(n: number): number[] {
  const out = new Array<number>(n);
  for (let i = 0; i < n; i++) out[i] = i;
  return out;
}

// --------------------------------------------------------------------------- //
// Drawdown
// --------------------------------------------------------------------------- //

function drawdownSeries(returns: number[]): number[] {
  const out = new Array<number>(returns.length);
  let eq = 100;
  let peak = 100;
  for (let i = 0; i < returns.length; i++) {
    eq *= 1 + returns[i];
    if (eq > peak) peak = eq;
    out[i] = Math.min(eq / peak - 1, 0);
  }
  return out;
}

export function maxDrawdown(returns: number[]): number {
  const dd = drawdownSeries(returns);
  if (dd.length === 0) return 0;
  let m = dd[0];
  for (let i = 1; i < dd.length; i++) if (dd[i] < m) m = dd[i];
  return m;
}

// --------------------------------------------------------------------------- //
// Historical VaR
// --------------------------------------------------------------------------- //

function historicalVar(
  p: Record<string, number[]>,
  w: number[],
  levels: readonly number[],
): number[] {
  const pr = portfolioReturns(p, w, range(ROW_COUNT)).filter(finite);
  if (pr.length === 0) {
    throw new Error("No finite portfolio returns available to compute VaR.");
  }
  pr.sort((a, b) => a - b);
  return levels.map((cl) => -percentile(pr, (1 - cl) * 100));
}

// --------------------------------------------------------------------------- //
// Monte Carlo VaR (multivariate Normal, seeded)
// --------------------------------------------------------------------------- //

/** Deterministic PRNG (mulberry32) so MC VaR is reproducible across calls. */
function makeRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Seeded standard-normal generator (Box-Muller transform). */
function makeGaussian(rng: () => number): () => number {
  let spare: number | null = null;
  return () => {
    if (spare !== null) {
      const v = spare;
      spare = null;
      return v;
    }
    let u = rng();
    while (u <= 1e-12) u = rng(); // keep log argument away from zero
    const v = rng();
    const mag = Math.sqrt(-2 * Math.log(u));
    spare = mag * Math.sin(2 * Math.PI * v);
    return mag * Math.cos(2 * Math.PI * v);
  };
}

/** Lower-triangular Cholesky factor of a positive-definite matrix. */
function cholesky(a: number[][]): number[][] {
  const n = a.length;
  const l = a.map((row) => row.map(() => 0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let s = a[i]?.[j] ?? 0;
      for (let k = 0; k < j; k++) s -= (l[i]?.[k] ?? 0) * (l[j]?.[k] ?? 0);
      if (i === j) l[i][j] = Math.sqrt(Math.max(s, 0));
      else l[i][j] = s / (l[j]?.[j] ?? 1);
    }
  }
  return l;
}

/** Mean vector + sample covariance (ddof=1) of the tradable asset returns. */
function estimateMoments(p: Record<string, number[]>): {
  mu: number[];
  cov: number[][];
} {
  const k = TICKERS.length;
  const cols = TICKERS.map((t) => p[t] as number[]);
  const rows: number[][] = [];
  for (let r = 0; r < ROW_COUNT; r++) {
    const row = cols.map((c) => c[r] as number);
    if (row.every(finite)) rows.push(row);
  }
  if (rows.length < 3) {
    throw new Error("Not enough observations to estimate covariance.");
  }
  const m = rows.length;
  const mu = new Array<number>(k);
  const cov: number[][] = [];
  for (let i = 0; i < k; i++) {
    let s = 0;
    for (let r = 0; r < m; r++) s += rows[r][i];
    mu[i] = s / m;
  }
  for (let i = 0; i < k; i++) {
    cov[i] = new Array<number>(k);
    for (let j = 0; j < k; j++) {
      let s = 0;
      for (let r = 0; r < m; r++) {
        s += (rows[r][i] - mu[i]) * (rows[r][j] - mu[j]);
      }
      cov[i][j] = s / (m - 1);
    }
  }
  return { mu, cov };
}

function monteCarloVar(
  p: Record<string, number[]>,
  w: number[],
  levels: readonly number[],
): number[] {
  const { mu, cov } = estimateMoments(p);
  const l = cholesky(cov);
  const gauss = makeGaussian(makeRng(MONTE_CARLO.randomSeed));
  const k = mu.length;
  const scenarios: number[] = [];

  for (let s = 0; s < MONTE_CARLO.nScenarios; s++) {
    const z = new Array<number>(k);
    for (let i = 0; i < k; i++) z[i] = gauss();
    const x = new Array<number>(k);
    for (let i = 0; i < k; i++) {
      let sum = 0;
      for (let j = 0; j < k; j++) sum += (l[i]?.[j] ?? 0) * z[j];
      x[i] = mu[i] + sum;
    }
    let port = 0;
    for (let i = 0; i < k; i++) port += x[i] * w[i];
    if (finite(port)) scenarios.push(port);
  }

  scenarios.sort((a, b) => a - b);
  return levels.map((cl) => -percentile(scenarios, (1 - cl) * 100));
}

// --------------------------------------------------------------------------- //
// Beta
// --------------------------------------------------------------------------- //

function assetBetas(p: Record<string, number[]>): Record<string, number> {
  const bench = p[BENCHMARK] as number[];
  const benchFinite = bench.filter(finite);
  if (benchFinite.length < 2) {
    throw new Error("Not enough benchmark observations to compute beta.");
  }
  const varBench = variance(benchFinite, 1);
  if (varBench <= 0) {
    throw new Error("Benchmark variance is zero - beta is undefined.");
  }

  const betas: Record<string, number> = {};
  for (const t of TICKERS) {
    const a = p[t] as number[];
    const am: number[] = [];
    const bm: number[] = [];
    for (let i = 0; i < a.length; i++) {
      if (finite(a[i]) && finite(bench[i])) {
        am.push(a[i]);
        bm.push(bench[i]);
      }
    }
    betas[t] = covariance(am, bm, 1) / varBench;
  }
  return betas;
}

function portfolioBeta(
  p: Record<string, number[]>,
  w: number[],
): number {
  const ab = assetBetas(p);
  let sum = 0;
  for (let i = 0; i < TICKERS.length; i++) sum += ab[TICKERS[i] as string] * w[i];
  return sum;
}

// --------------------------------------------------------------------------- //
// Stress tests
// --------------------------------------------------------------------------- //

function stressTests(
  p: Record<string, number[]>,
  w: number[],
): StressResult[] {
  const allDates = dates();
  const firstDate = allDates[0] as string;
  const lastDate = allDates[allDates.length - 1] as string;

  return STRESS_WINDOWS.map((win: StressWindow): StressResult => {
    // Windows entirely outside the fetched range are reported as skipped.
    if (win.end < firstDate || win.start > lastDate) {
      return {
        ...win,
        projected_drawdown: null,
        total_return: null,
        n_obs: 0,
        skipped: true,
        note: `Data sample ${firstDate}..${lastDate} does not cover this window.`,
      };
    }

    const rows: number[] = [];
    for (let i = 0; i < allDates.length; i++) {
      const d = allDates[i] as string;
      if (d >= win.start && d <= win.end) rows.push(i);
    }

    const pr = portfolioReturns(p, w, rows).filter(finite);
    if (pr.length === 0) {
      throw new Error(`Stress window ${win.key} produced no portfolio returns.`);
    }

    const dd = maxDrawdown(pr);
    const totalReturn = pr.reduce((acc, r) => acc * (1 + r), 1) - 1;

    return {
      ...win,
      projected_drawdown: -dd,
      total_return: totalReturn,
      n_obs: pr.length,
      skipped: false,
      note: "",
    };
  });
}

// --------------------------------------------------------------------------- //
// Orchestration (mirrors backend services/analysis.py run_analysis / health)
// --------------------------------------------------------------------------- //

export interface VarResult {
  p95: number;
  p99: number;
}

export interface StressResult {
  key: string;
  label: string;
  start: string;
  end: string;
  event: string;
  projected_drawdown: number | null;
  total_return: number | null;
  n_obs: number;
  skipped: boolean;
  note: string;
}

export interface AnalysisResult {
  tickers: string[];
  weights_norm: Record<string, number>;
  dates: string[];
  portfolio_returns: number[];
  benchmark_returns: number[];
  equity_curve: number[];
  benchmark_equity: number[];
  var: { historical: VarResult; monte_carlo: VarResult };
  max_drawdown: number;
  asset_betas: Record<string, number>;
  portfolio_beta: number;
  stress: StressResult[];
  data_start: string;
  data_end: string;
  n_obs: number;
}

export interface HealthPayload {
  status: "ok";
  n_obs: number;
  data_start: string;
  data_end: string;
  cache_seconds: number;
}

export function analyze(weights: Record<string, number>): AnalysisResult {
  const p = panel();
  const allDates = dates();
  const w = normalizeWeights(weights);

  // Portfolio-return series over the whole sample (aligned with the panel
  // index), then keep only finite rows -> the same index used by everything
  // downstream (benchmark series, equity curves, dates).
  const raw = portfolioReturns(p, w, range(ROW_COUNT));
  const keep: number[] = [];
  for (let i = 0; i < raw.length; i++) if (finite(raw[i])) keep.push(i);

  const datesOut = keep.map((i) => allDates[i] as string);
  const portfolioRets = keep.map((i) => raw[i] as number);
  const benchRets = keep.map((i) => {
    const v = (p[BENCHMARK] as number[])[i] as number;
    return finite(v) ? v : 0;
  });

  const equity = cumulativeEquity(portfolioRets);
  const benchEquity = cumulativeEquity(benchRets);

  const hvar = historicalVar(p, w, [0.95, 0.99]);
  const mcvar = monteCarloVar(p, w, [0.95, 0.99]);
  const ab = assetBetas(p);
  const maxDd = maxDrawdown(portfolioRets);

  return {
    tickers: [...TICKERS],
    weights_norm: Object.fromEntries(
      TICKERS.map((t, i) => [t, roundDec(w[i], 6)]),
    ),
    dates: datesOut,
    portfolio_returns: portfolioRets.map((v) => roundDec(v, 8)),
    benchmark_returns: benchRets.map((v) => roundDec(v, 8)),
    equity_curve: equity.map((v) => roundDec(v, 6)),
    benchmark_equity: benchEquity.map((v) => roundDec(v, 6)),
    var: {
      historical: { p95: roundDec(hvar[0], 6), p99: roundDec(hvar[1], 6) },
      monte_carlo: { p95: roundDec(mcvar[0], 6), p99: roundDec(mcvar[1], 6) },
    },
    max_drawdown: roundDec(maxDd, 6),
    asset_betas: Object.fromEntries(
      TICKERS.map((t) => [t, roundDec(ab[t as string], 6)]),
    ),
    portfolio_beta: roundDec(portfolioBeta(p, w), 6),
    stress: stressTests(p, w),
    data_start: datesOut[0] ?? "",
    data_end: datesOut[datesOut.length - 1] ?? "",
    n_obs: datesOut.length,
  };
}

export function health(): HealthPayload {
  const allDates = dates();
  return {
    status: "ok",
    n_obs: allDates.length,
    data_start: allDates[0] as string,
    data_end: allDates[allDates.length - 1] as string,
    cache_seconds: CACHE_MAX_AGE_SECONDS,
  };
}