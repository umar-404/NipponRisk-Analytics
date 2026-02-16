import { useEffect, useRef, useState } from "react";
import PortfolioChart from "../components/PortfolioChart";
import StatCard from "../components/StatCard";
import StressGrid from "../components/StressGrid";
import WeightSliders from "../components/WeightSliders";
import { analyze } from "../lib/api";
import { fmt, pctLoss } from "../lib/format";
import { AnalysisResult, TICKERS, TICKER_NAMES, Weights } from "../types";

const DEFAULT_WEIGHTS: Weights = Object.fromEntries(
  TICKERS.map((t) => [t, 100 / TICKERS.length]),
);

export default function Dashboard() {
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focusWindowKey, setFocusWindowKey] = useState<string | null>(null);

  // Debounce live recompute so rapid slider drags don't spam the API.
  const timer = useRef<number | null>(null);
  const requestSeq = useRef(0);

  useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const seq = ++requestSeq.current;
      setLoading(true);
      setError(null);
      analyze(weights)
        .then((res) => {
          if (seq === requestSeq.current) {
            setResult(res);
            setLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (seq === requestSeq.current) {
            setError(err instanceof Error ? err.message : "Unable to reach the backend.");
            setLoading(false);
          }
        });
    }, 350);

    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      requestSeq.current += 1;
    };
  }, [weights]);

  const normalized = result
    ? result.weights_norm
    : Object.fromEntries(TICKERS.map((t) => [t, 1 / TICKERS.length]));

  const varValues = result
    ? {
        hist95: pctLoss(result.var.historical.p95, 2),
        hist99: pctLoss(result.var.historical.p99, 2),
        mc95: pctLoss(result.var.monte_carlo.p95, 2),
        mc99: pctLoss(result.var.monte_carlo.p99, 2),
      }
    : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <header className="mb-6 flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🎌</span>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">NipponRisk Analytics</h1>
            <p className="text-sm text-slate-500">
              Portfolio risk &amp; stress-testing for Japanese equities (
              {TICKERS.map((t) => TICKER_NAMES[t]).join(", ")})
            </p>
          </div>
        </div>
        {result && (
          <p className="mt-1 text-xs text-slate-400">
            Sample: {result.data_start.slice(0, 10)} → {result.data_end.slice(0, 10)} ·{" "}
            {result.n_obs.toLocaleString()} trading days
          </p>
        )}
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <strong>Error:</strong> {error}. Is the backend running at{" "}
          <code className="rounded bg-rose-100 px-1">http://localhost:8000</code>?
        </div>
      )}

      {/* Metrics */}
      <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard
          label="Hist VaR 95%"
          value={result && varValues ? varValues.hist95 : "—"}
          sub="1-day, historical"
          tone="text-rose-600"
        />
        <StatCard
          label="Hist VaR 99%"
          value={result && varValues ? varValues.hist99 : "—"}
          sub="1-day, historical"
          tone="text-rose-600"
        />
        <StatCard
          label="MC VaR 95%"
          value={result && varValues ? varValues.mc95 : "—"}
          sub="1-day, Monte Carlo"
          tone="text-amber-600"
        />
        <StatCard
          label="MC VaR 99%"
          value={result && varValues ? varValues.mc99 : "—"}
          sub="1-day, Monte Carlo"
          tone="text-amber-600"
        />
        <StatCard
          label="Max Drawdown"
          value={result ? pctLoss(Math.abs(result.max_drawdown), 1) : "—"}
          sub="full sample, worst peak→trough"
          tone="text-rose-600"
        />
        <StatCard
          label="Portfolio Beta"
          value={result ? fmt(result.portfolio_beta, 2) : "—"}
          sub="vs Nikkei 225"
          tone="text-sky-600"
        />
      </section>

      {/* Body: controls + chart */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-6">
          <WeightSliders weights={weights} onWeightsChange={setWeights} />
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Asset Betas</h3>
            <ul className="space-y-1 text-sm">
              {TICKERS.map((t) => (
                <li key={t} className="flex items-center justify-between">
                  <span className="text-slate-600">{TICKER_NAMES[t]}</span>
                  <span className="tabular-nums text-slate-800">
                    {result ? fmt(result.asset_betas[t], 2) : "—"}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] leading-snug text-slate-400">
              Normalized weights:{" "}
              {Object.entries(normalized)
                .map(([t, w]) => `${TICKER_NAMES[t]} ${(w * 100).toFixed(0)}%`)
                .join(" · ")}
            </p>
          </div>
        </aside>

        <div className="space-y-6">
          <PortfolioChart result={result} focusWindowKey={focusWindowKey} />
          <StressGrid
            stress={result?.stress ?? []}
            focusWindowKey={focusWindowKey}
            onSelectWindow={setFocusWindowKey}
          />
        </div>
      </section>

      {loading && (
        <div className="pointer-events-none fixed bottom-4 right-4 rounded-full bg-slate-900 px-4 py-2 text-xs text-white shadow-lg">
          Recalculating…
        </div>
      )}
    </div>
  );
}