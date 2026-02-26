# NipponRisk Analytics — Vercel serverless function for GET /api/health.

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from app.services.analysis import health_payload  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            self._send(200, health_payload())
        except FileNotFoundError as exc:
            self._send(503, {"detail": str(exc)})
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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")