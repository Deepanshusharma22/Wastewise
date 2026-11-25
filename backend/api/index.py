"""Vercel Python entry point: exposes the FastAPI ASGI app.

All paths are rewritten here by vercel.json. The app also runs unchanged under uvicorn/Docker
(`uvicorn app.main:app`), so the hosting platform stays swappable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
