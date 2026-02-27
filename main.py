# NipponRisk Analytics — Vercel FastAPI preset entrypoint.
#
# Vercel auto-detects the FastAPI framework preset and needs a FastAPI instance
# named `app` at a recognized entrypoint (root main.py/app.py/...). This thin
# shim re-exports the real backend app from backend/app/main.py so the app that
# runs locally (`uvicorn app.main:app`) deploys as-is on Vercel.
#
# This file is only loaded by Vercel's build. Local development never imports
# it — `uvicorn app.main:app` loads backend/app/main.py directly.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.main import app  # noqa: E402