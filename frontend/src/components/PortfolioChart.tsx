import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AnalysisResult, StressResult } from "../types";

interface PortfolioChartProps {
  result: AnalysisResult | null;
  /** If set, zoom the chart into a single stress window's date range. */
  focusWindowKey?: string | null;
}

interface Datum {
  date: string;
  portfolio: number;
  benchmark: number;
}

/** Downsample a series to at most `maxPoints` points for chart performance. */
function downsample(
  dates: string[],
  portfolio: number[],
  benchmark: number[],
  maxPoints = 600,
): Datum[] {
  const n = dates.length;
  if (n <= maxPoints) {
    return dates.map((date, i) => ({
      date,
      portfolio: portfolio[i],
      benchmark: benchmark[i],
    }));
  }
  const step = n / maxPoints;
  const out: Datum[] = [];
  for (let k = 0; k < maxPoints; k++) {
    const i = Math.min(n - 1, Math.floor(k * step));
    out.push({
      date: dates[i],
      portfolio: portfolio[i],
      benchmark: benchmark[i],
    });
  }
  return out;
}

/** Day string ("2024-07-01") from a full ISO date. */
const day = (iso: string) => iso.slice(0, 10);

/** Slice the FULL series to a window's date range (inclusive, day-level). */
function sliceToWindow(
  result: AnalysisResult,
  window: StressResult,
): { dates: string[]; equity: number[]; benchmark: number[] } {
  const dates: string[] = [];
  const equity: number[] = [];
  const benchmark: number[] = [];
  for (let i = 0; i < result.dates.length; i++) {
    const d = day(result.dates[i]);
    if (d >= window.start && d <= window.end) {
      dates.push(result.dates[i]);
      equity.push(result.equity_curve[i]);
      benchmark.push(result.benchmark_equity[i]);
    }
  }
  return { dates, equity, benchmark };
}

interface Shaded extends StressResult {
  x1: string;
  x2: string;
}

export default function PortfolioChart({ result, focusWindowKey }: PortfolioChartProps) {
  const hasResult = result !== null;
  const focusWindow = focusWindowKey && result
    ? result.stress.find((s) => s.key === focusWindowKey)
    : undefined;

  // Zoomed view: slice the FULL series to the focused window, then downsample
  // that slice. Overview view: downsample the whole sample.
  const data: Datum[] = (() => {
    if (!hasResult) return [];
    if (focusWindow) {
      const w = sliceToWindow(result, focusWindow);
      return downsample(w.dates, w.equity, w.benchmark, 120);
    }
    return downsample(result.dates, result.equity_curve, result.benchmark_equity);
  })();

  // Stress windows shaded as reference areas (overview view only). The XAxis
  // is categorical, so x1/x2 must be labels that exist on the axis — snap them
  // to the nearest plotted point instead of using the raw window bounds.
  const areas: Shaded[] = (() => {
    if (!hasResult || focusWindow) return [];
    return result.stress
      .filter((s) => !s.skipped)
      .map((s): Shaded | null => {
        const first = data.find((d) => day(d.date) >= s.start);
        const last = [...data].reverse().find((d) => day(d.date) <= s.end);
        return first && last ? { ...s, x1: first.date, x2: last.date } : null;
      })
      .filter((s): s is Shaded => s !== null);
  })();

  const minY = hasResult && data.length
    ? Math.min(...data.map((d) => Math.min(d.portfolio, d.benchmark))) * 0.99
    : 0;
  const maxY = hasResult && data.length
    ? Math.max(...data.map((d) => Math.max(d.portfolio, d.benchmark))) * 1.01
    : 100;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Performance (indexed to 100)</h3>
        {focusWindow && (
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700">
            Focus: {focusWindow.label}
          </span>
        )}
      </div>

      {data.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400">
          {focusWindow
            ? `No data for ${focusWindow.label} (${focusWindow.start} → ${focusWindow.end}).`
            : "No data to display."}
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => day(d)}
              minTickGap={30}
              tick={{ fontSize: 11, fill: "#64748b" }}
            />
            <YAxis
              domain={[minY, maxY]}
              tick={{ fontSize: 11, fill: "#64748b" }}
              tickFormatter={(v: number) => v.toFixed(0)}
              width={56}
            />

            {areas.map((s) => (
              <ReferenceArea
                key={s.key}
                x1={s.x1}
                x2={s.x2}
                fill="#f59e0b"
                fillOpacity={0.14}
                stroke="#f59e0b"
                strokeOpacity={0.4}
                ifOverflow="extendDomain"
              />
            ))}

            <Tooltip
              formatter={(value) => [Number(value).toFixed(2), ""]}
              labelFormatter={(label) => day(String(label))}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              type="monotone"
              dataKey="portfolio"
              name="Portfolio"
              dot={false}
              stroke="#7b1fa2"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              name="Nikkei 225"
              dot={false}
              stroke="#0f766e"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
