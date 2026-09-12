// NipponRisk Analytics
// App configuration mirroring backend/app/config.py (single source of truth for
// the Cloudflare Worker risk engine).

export const TICKERS = ["7203.T", "6758.T", "8306.T", "9432.T"] as const;

export const BENCHMARK = "^N225"; // Nikkei 225

// Display names (the frontend falls back to the ticker if absent).
export const TICKER_NAMES: Record<string, string> = {
  "7203.T": "Toyota",
  "6758.T": "Sony",
  "8306.T": "MUFG",
  "9432.T": "NTT",
  "^N225": "Nikkei 225",
};

// Data freshness reported by /api/health (mirrors backend CACHE_MAX_AGE_SECONDS).
export const CACHE_MAX_AGE_SECONDS = 60 * 60 * 24;

export interface StressWindow {
  key: string;
  label: string;
  start: string; // ISO date, inclusive
  end: string; // ISO date, inclusive
  event: string;
}

export const STRESS_WINDOWS: StressWindow[] = [
  {
    key: "yen-spike-2024",
    label: "Aug 2024 Yen-Spike Crash",
    start: "2024-07-01",
    end: "2024-08-31",
    event:
      "Bank of Japan rate hike triggered a yen spike and one of the Nikkei's worst single-day crashes.",
  },
  {
    key: "covid-2020",
    label: "March 2020 COVID Shock",
    start: "2020-01-31",
    end: "2020-04-30",
    event: "Global pandemic sell-off and acute market stress.",
  },
];

// Monte Carlo parameters (mirrors backend MonteCarloParams).
export const MONTE_CARLO = {
  nScenarios: 10_000,
  confidenceLevels: [0.95, 0.99] as const,
  randomSeed: 42,
};