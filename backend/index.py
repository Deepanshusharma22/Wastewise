"""Vercel entry point for Git deployments (project root directory `backend/`, framework preset FastAPI).

Vercel's FastAPI preset detects this root-level `index.py` and routes every path to `app`.
The app also runs unchanged under uvicorn/Docker (`uvicorn app.main:app`), so the hosting
platform stays swappable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402,F401
