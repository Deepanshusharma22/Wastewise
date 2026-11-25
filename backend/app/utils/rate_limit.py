"""Per-user sliding-window rate limiter (in-process).

Keyed by the authenticated user id (falls back to client IP), so one user cannot exhaust the CPU
budget of the inference endpoint. State is per process: with several replicas, put a shared store
(e.g. Redis) behind the same interface.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limits: list[tuple[int, int]], now: float | None = None) -> None:
        """limits: [(max_requests, window_seconds), ...]. Raises 429 when any limit is exceeded."""
        now = time.monotonic() if now is None else now
        longest = max(w for _, w in limits)
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > longest:
                q.popleft()
            for max_req, window in limits:
                in_window = sum(1 for t in q if now - t <= window)
                if in_window >= max_req:
                    oldest = next(t for t in q if now - t <= window)
                    retry = max(1, int(window - (now - oldest)) + 1)
                    raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                        detail={"code": "rate_limited",
                                                "message": f"Too many requests. Try again in {retry} s."},
                                        headers={"Retry-After": str(retry)})
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_key(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if uid:
        return f"user:{uid}"
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"
