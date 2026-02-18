/** Number / percentage formatting helpers. */

/** Format a decimal as a signed percentage, e.g. 0.123 -> "+12.30%". */
export function pct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

/** Format a decimal risk/loss figure as an unsigned percentage, e.g. 0.123 -> "12.30%". */
export function pctLoss(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Format a number with fixed decimals. */
export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** Format an ISO date string to `YYYY-MM-DD` (or "—" if empty). */
export function shortDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10);
}