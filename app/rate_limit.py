"""Simple in-memory per-IP rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    max_requests: int = 30
    window_seconds: int = 60
    _hits: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def check(self, client_ip: str) -> bool:
        """Return True if request is allowed, False if rate limit exceeded."""
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[client_ip]
        self._hits[client_ip] = [t for t in hits if t > window_start]
        if len(self._hits[client_ip]) >= self.max_requests:
            return False
        self._hits[client_ip].append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
