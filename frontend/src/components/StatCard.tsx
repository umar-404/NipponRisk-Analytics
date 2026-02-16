interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  /** Tailwind text color class, e.g. "text-emerald-600". */
  tone?: string;
}

/** A compact KPI tile for a single metric (VaR, drawdown, beta). */
export default function StatCard({ label, value, sub, tone = "text-slate-800" }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}