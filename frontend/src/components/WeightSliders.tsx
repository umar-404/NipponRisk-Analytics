import { TICKERS, TICKER_NAMES, Weights } from "../types";

interface WeightSlidersProps {
  weights: Weights;
  onWeightsChange: (next: Weights) => void;
}

/** Dynamic per-asset weight sliders + number inputs with a sum indicator. */
export default function WeightSliders({ weights, onWeightsChange }: WeightSlidersProps) {
  const total = TICKERS.reduce((acc, t) => acc + (weights[t] ?? 0), 0);
  const off = Math.abs(total - 100) > 0.5;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Portfolio Weights</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            off ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
          }`}
        >
          {total.toFixed(1)}%
        </span>
      </div>

      <div className="space-y-4">
        {TICKERS.map((t) => {
          const value = weights[t] ?? 0;
          return (
            <div key={t}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">
                  {TICKER_NAMES[t]}{" "}
                  <span className="text-xs text-slate-400">({t})</span>
                </span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={Math.round(value)}
                  onChange={(e) => {
                    const v = Number(e.target.value) || 0;
                    onWeightsChange({ ...weights, [t]: Math.max(0, Math.min(100, v)) });
                  }}
                  className="w-16 rounded border border-slate-300 px-2 py-0.5 text-right text-sm focus:border-brand focus:outline-none"
                  aria-label={`${TICKER_NAMES[t]} weight percent`}
                />
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={Math.round(value)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  onWeightsChange({ ...weights, [t]: v });
                }}
                className="w-full accent-brand-700"
                aria-label={`${TICKER_NAMES[t]} weight slider`}
              />
            </div>
          );
        })}
      </div>

      {off && (
        <p className="mt-3 text-xs text-amber-600">
          Weights don&apos;t sum to 100% — the backend normalizes them; adding to
          100% is recommended.
        </p>
      )}
    </div>
  );
}