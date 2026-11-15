"""API authentication, role checks and rate limiting."""

import hmac
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status

ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


@dataclass(frozen=True)
class Principal:
    name: str
    role: str

    @property
    def actor(self) -> str:
        return f"api:{self.name}"


class RateLimiter:
    """Sliding one-minute window per caller, kept in process memory."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, caller: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(caller, deque())
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True


class Authenticator:
    def __init__(self, keys: dict[str, tuple[str, str]], limiter: RateLimiter) -> None:
        self._keys = {key.encode(): Principal(name, role) for key, (name, role) in keys.items()}
        self._limiter = limiter

    def authenticate(self, presented: str | None) -> Principal:
        if not presented:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
        candidate = presented.encode()
        principal = None
        for key, owner in self._keys.items():  # compare against every key: no early exit
            if hmac.compare_digest(key, candidate):
                principal = owner
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        if not self._limiter.allow(principal.name):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
        return principal

    def require(self, minimum_role: str) -> Callable[..., Principal]:
        def dependency(x_api_key: Annotated[str | None, Header()] = None) -> Principal:
            principal = self.authenticate(x_api_key)
            if ROLE_RANK[principal.role] < ROLE_RANK[minimum_role]:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, f"Requires the '{minimum_role}' role"
                )
            return principal

        return dependency
