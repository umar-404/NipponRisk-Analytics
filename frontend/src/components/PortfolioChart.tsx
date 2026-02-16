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

export default function PortfolioChart({ result, focusWindowKey }: PortfolioChartProps) {
  const hasResult = result !== null;
  const data = hasResult
    ? downsample(result.dates, result.equity_curve, result.benchmark_equity)
    : [];
  const focusWindow = focusWindowKey && result
    ? result.stress.find((s) => s.key === focusWindowKey)
    : undefined;

  // Stress windows rendered as reference areas when not zoomed into one.
  const areas: StressResult[] = focusWindow || !result
    ? []
    : result.stress.filter((s) => !s.skipped);

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
        <p className="py-10 text-center text-sm text-slate-400">No data to display.</p>
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => d.slice(0, 7)}
              minTickGap={40}
              tick={{ fontSize: 11, fill: "#64748b" }}
            />
            <YAxis
              domain={[minY, maxY]}
              tick={{ fontSize: 11, fill: "#64748b" }}
              tickFormatter={(v: number) => v.toFixed(0)}
              width={56}
            />

            {!focusWindow &&
              areas.map((s) => (
                <ReferenceArea
                  key={s.key}
                  x1={s.start}
                  x2={s.end}
                  fill="#f59e0b"
                  fillOpacity={0.12}
                  stroke="#f59e0b"
                  strokeOpacity={0.4}
                  ifOverflow="discard"
                />
              ))}

            <Tooltip
              formatter={(value) => [Number(value).toFixed(2), ""]}
              labelFormatter={(label) => String(label)}
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