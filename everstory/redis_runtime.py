"""Redis-backed session coordination with a safe single-process fallback."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from threading import RLock
from typing import Iterator


class RedisRuntime:
    def __init__(
        self,
        url: str = "",
        *,
        session_ttl: int = 2_592_000,
        rate_limit: int = 0,
        rate_window: int = 60,
        strict: bool = False,
    ):
        self.url = url.strip()
        self.session_ttl = max(60, session_ttl)
        self.rate_limit = max(0, rate_limit)
        self.rate_window = max(1, rate_window)
        self.strict = strict
        self._client = None
        self._error = ""
        self._local_guard = RLock()
        self._local_locks: dict[str, RLock] = {}
        self._local_buckets: dict[str, tuple[int, int]] = {}
        if self.url:
            try:
                import redis

                self._client = redis.Redis.from_url(
                    self.url, decode_responses=True, socket_connect_timeout=2
                )
            except Exception as exc:  # pragma: no cover - optional dependency
                self._fail(exc)

    @property
    def name(self) -> str:
        return "redis" if self.url else "memory"

    def _fail(self, exc: Exception) -> None:
        self._error = str(exc)[:160]
        if self.strict:
            raise RuntimeError(f"Redis unavailable: {self._error}") from exc

    def touch(self, session_id: str) -> None:
        if self._client is None:
            return
        try:
            self._client.setex(f"everstory:session:{session_id}", self.session_ttl, "1")
        except Exception as exc:  # pragma: no cover - external service
            self._fail(exc)

    def allow(self, key: str) -> tuple[bool, int]:
        """Fixed-window request quota. Returns (allowed, remaining)."""
        if self.rate_limit <= 0:
            return True, -1
        window = int(time.time()) // self.rate_window
        bucket = f"everstory:rate:{key}:{window}"
        if self._client is not None:
            try:
                pipe = self._client.pipeline()
                pipe.incr(bucket)
                pipe.expire(bucket, self.rate_window + 1)
                count, _ = pipe.execute()
                return count <= self.rate_limit, max(0, self.rate_limit - count)
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        with self._local_guard:
            seen_window, count = self._local_buckets.get(key, (window, 0))
            count = count + 1 if seen_window == window else 1
            self._local_buckets[key] = (window, count)
            return count <= self.rate_limit, max(0, self.rate_limit - count)

    @contextmanager
    def session_lock(self, session_id: str) -> Iterator[None]:
        if self._client is not None:
            lock = None
            try:
                lock = self._client.lock(
                    f"everstory:lock:{session_id}", timeout=130, blocking_timeout=10
                )
                if not lock.acquire(blocking=True):
                    raise RuntimeError("Session is busy; retry shortly.")
            except RuntimeError:
                raise
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
            if lock is not None and lock.owned():
                try:
                    yield
                finally:
                    try:
                        lock.release()
                    except Exception as exc:  # lock expiry must never repeat the mutation
                        self._fail(exc)
                return
        with self._local_guard:
            lock = self._local_locks.setdefault(session_id, RLock())
        with lock:
            yield

    def health(self) -> dict:
        if self._client is None:
            return {"backend": self.name, "ok": not self.strict, "error": self._error}
        try:
            self._client.ping()
            return {"backend": "redis", "ok": True}
        except Exception as exc:  # pragma: no cover - external service
            self._error = str(exc)[:160]
            return {"backend": "redis", "ok": False, "error": self._error}


def build_redis_runtime() -> RedisRuntime:
    return RedisRuntime(
        os.getenv("REDIS_URL", ""),
        session_ttl=int(os.getenv("SESSION_TTL_SECONDS", "2592000")),
        rate_limit=int(os.getenv("RATE_LIMIT_REQUESTS", "0")),
        rate_window=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        strict=os.getenv("INFRA_STRICT", "false").lower() in {"1", "true", "yes"},
    )
