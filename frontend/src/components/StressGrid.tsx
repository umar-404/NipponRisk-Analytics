import { StressResult } from "../types";
import { pct } from "../lib/format";

interface StressGridProps {
  stress: StressResult[];
  focusWindowKey: string | null;
  onSelectWindow: (key: string | null) => void;
}

/** Cards summarizing the projected impact of each historical stress window. */
export default function StressGrid({
  stress,
  focusWindowKey,
  onSelectWindow,
}: StressGridProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Historical Stress Tests</h3>
        {focusWindowKey && (
          <button
            onClick={() => onSelectWindow(null)}
            className="text-xs text-brand-700 hover:underline"
          >
            Clear focus
          </button>
        )}
      </div>

      {stress.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-400">No stress windows configured.</p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {stress.map((s) => {
          const focused = s.key === focusWindowKey;
          const unavailable = s.skipped || s.projected_drawdown === null;
          return (
            <button
              key={s.key}
              onClick={() => onSelectWindow(focused ? null : s.key)}
              className={`rounded-lg border p-3 text-left transition-colors ${
                focused
                  ? "border-brand-700 bg-brand-50"
                  : "border-slate-200 bg-slate-50 hover:border-brand-500"
              }`}
              title="Click to focus the chart on this window"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-700">{s.label}</p>
                <span className="text-[11px] text-slate-400">
                  {s.start} → {s.end}
                </span>
              </div>

              {unavailable ? (
                <p className="mt-2 text-xs text-slate-400">
                  No data available for this window ({s.n_obs} obs).
                </p>
              ) : (
                <>
                  <p className="mt-2 text-2xl font-semibold text-rose-600 tabular-nums">
                    -{pct(s.projected_drawdown, 1)}
                  </p>
                  <p className="text-xs text-slate-500">projected max drawdown</p>
                  <div className="mt-2 flex justify-between text-xs text-slate-500">
                    <span>window total:</span>
                    <span className="tabular-nums">{pct(s.total_return ?? 0, 1)}</span>
                  </div>
                  <div className="mt-1 flex justify-between text-xs text-slate-400">
                    <span>days in window:</span>
                    <span className="tabular-nums">{s.n_obs}</span>
                  </div>
                  {s.event && (
                    <p className="mt-2 text-[11px] leading-snug text-slate-400">{s.event}</p>
                  )}
                </>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}