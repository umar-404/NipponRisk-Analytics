// NipponRisk Analytics
// Cloudflare Worker entrypoint: routes /api/analyze + /api/health to the risk
// engine and falls through to the bundled static SPA (frontend/dist) via the
// ASSETS binding for everything else.

import type { Fetcher } from "@cloudflare/workers-types";

import { analyze, health } from "./risk";

export interface Env {
  ASSETS: Fetcher;
}

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  });
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    if (path === "/api/health" && method === "GET") {
      return json(200, health());
    }

    if (path === "/api/analyze" && method === "POST") {
      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return json(400, { detail: "Invalid JSON body." });
      }

      const weights = isRecord(body) ? body.weights : undefined;
      if (!isRecord(weights)) {
        return json(400, {
          detail: "Field 'weights' (object of ticker -> weight) is required.",
        });
      }

      try {
        return json(200, analyze(weights as Record<string, number>));
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Analysis failed.";
        return json(400, { detail: msg });
      }
    }

    // API paths the SPA never calls -> 404 JSON.
    if (path.startsWith("/api/")) {
      return json(404, { detail: "Not found." });
    }

    // Everything else is the SPA/static assets. Cloudflare only invokes this
    // Worker when no static asset matched, so ASSETS.fetch() applies the
    // configured not_found_handling (single-page-application) -> index.html.
    return env.ASSETS.fetch(request);
  },
};