# NipponRisk Analytics — Vercel serverless function for POST /api/analyze.
#
# File-based Python function: Vercel serves api/analyze.py at /api/analyze.
# It reuses the same backend analysis engine as local FastAPI dev, so the risk
# math is identical in both environments.

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from app.services.analysis import run_analysis  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            result = run_analysis(payload.get("weights", {}))
            self._send(200, result)
        except FileNotFoundError as exc:
            self._send(503, {"detail": str(exc)})
        except (ValueError, KeyError, TypeError) as exc:
            self._send(400, {"detail": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            self._send(500, {"detail": f"Internal error: {exc}"})

    def _send(self, status: int, data) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")