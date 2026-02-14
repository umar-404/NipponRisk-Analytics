// Types mirroring the FastAPI response schema (backend/app/schemas.py).

export const TICKERS = ["7203.T", "6758.T", "8306.T", "9432.T"] as const;
export const BENCHMARK = "^N225";

export const TICKER_NAMES: Record<string, string> = {
  "7203.T": "Toyota",
  "6758.T": "Sony",
  "8306.T": "MUFG",
  "9432.T": "NTT",
  "^N225": "Nikkei 225",
};

/** Tradable ticker -> weight (any scale; server normalizes). */
export type Weights = Record<string, number>;

export interface VarResult {
  p95: number;
  p99: number;
}

export interface VarBlock {
  historical: VarResult;
  monte_carlo: VarResult;
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
  var: VarBlock;
  max_drawdown: number;
  asset_betas: Record<string, number>;
  portfolio_beta: number;
  stress: StressResult[];
  data_start: string;
  data_end: string;
  n_obs: number;
}