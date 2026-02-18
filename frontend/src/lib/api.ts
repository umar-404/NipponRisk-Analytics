import { AnalysisResult, Weights } from "../types";

/**
 * Call the backend risk engine. Requests go to the same origin and are proxied
 * to the FastAPI server during dev by Vite (see vite.config.ts). For a custom
 * backend host, set VITE_API_BASE, e.g. "http://localhost:8000".
 */
const API_BASE = (import.meta.env?.VITE_API_BASE as string | undefined) ?? "";

export async function analyze(weights: Weights): Promise<AnalysisResult> {
  const resp = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights }),
  });

  if (!resp.ok) {
    let detail = `Request failed (HTTP ${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* ignore parse errors; fall back to generic detail */
    }
    throw new Error(detail);
  }

  return (await resp.json()) as AnalysisResult;
}

export async function fetchHealth(): Promise<Record<string, unknown>> {
  const resp = await fetch(`${API_BASE}/api/health`);
  if (!resp.ok) throw new Error(`Health check failed (HTTP ${resp.status})`);
  return (await resp.json()) as Record<string, unknown>;
}