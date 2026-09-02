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
        self._local_counters: dict[str, tuple[float, int]] = {}
        self._local_circuits: dict[str, tuple[int, float]] = {}
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
        return self.allow_quota(key, self.rate_limit, self.rate_window)

    def allow_quota(
        self, key: str, limit: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Apply an explicit fixed-window quota for auth or budget scopes."""
        limit = max(0, limit)
        window_seconds = max(1, window_seconds)
        if limit <= 0:
            return True, -1
        window = int(time.time()) // window_seconds
        bucket = f"everstory:rate:{key}:{window}"
        if self._client is not None:
            try:
                pipe = self._client.pipeline()
                pipe.incr(bucket)
                pipe.expire(bucket, window_seconds + 1)
                count, _ = pipe.execute()
                return count <= limit, max(0, limit - count)
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        with self._local_guard:
            seen_window, count = self._local_buckets.get(key, (window, 0))
            count = count + 1 if seen_window == window else 1
            self._local_buckets[key] = (window, count)
            return count <= limit, max(0, limit - count)

    def reserve_tokens(
        self, key: str, limit: int, amount: int, ttl_seconds: int
    ) -> tuple[bool, int]:
        """Atomically reserve a token estimate without exceeding ``limit``."""
        limit, amount, ttl_seconds = max(0, limit), max(0, amount), max(1, ttl_seconds)
        if limit <= 0 or amount <= 0:
            return True, self.counter_value(key)
        if self._client is not None:
            try:
                result = self._client.eval(
                    """
                    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
                    local requested = tonumber(ARGV[1])
                    local limit = tonumber(ARGV[2])
                    if current + requested > limit then return {0, current} end
                    local updated = redis.call('INCRBY', KEYS[1], requested)
                    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
                    return {1, updated}
                    """,
                    1, key, amount, limit, ttl_seconds,
                )
                return bool(int(result[0])), int(result[1])
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        now = time.time()
        with self._local_guard:
            expires_at, current = self._local_counters.get(key, (now + ttl_seconds, 0))
            if expires_at <= now:
                expires_at, current = now + ttl_seconds, 0
            if current + amount > limit:
                self._local_counters[key] = (expires_at, current)
                return False, current
            current += amount
            self._local_counters[key] = (expires_at, current)
            return True, current

    def adjust_tokens(self, key: str, delta: int, ttl_seconds: int) -> int:
        """Settle a reservation against actual provider usage, clamped at zero."""
        ttl_seconds = max(1, ttl_seconds)
        if self._client is not None:
            try:
                result = self._client.eval(
                    """
                    local updated = tonumber(redis.call('INCRBY', KEYS[1], ARGV[1]))
                    if updated < 0 then redis.call('SET', KEYS[1], 0); updated = 0 end
                    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
                    return updated
                    """,
                    1, key, int(delta), ttl_seconds,
                )
                return int(result)
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        now = time.time()
        with self._local_guard:
            expires_at, current = self._local_counters.get(key, (now + ttl_seconds, 0))
            if expires_at <= now:
                expires_at, current = now + ttl_seconds, 0
            current = max(0, current + int(delta))
            self._local_counters[key] = (expires_at, current)
            return current

    def counter_value(self, key: str) -> int:
        if self._client is not None:
            try:
                return int(self._client.get(key) or 0)
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        now = time.time()
        with self._local_guard:
            expires_at, current = self._local_counters.get(key, (0, 0))
            if expires_at <= now:
                self._local_counters.pop(key, None)
                return 0
            return current

    def circuit_status(self, key: str) -> dict:
        if self._client is not None:
            try:
                ttl = int(self._client.ttl(f"{key}:open"))
                failures = int(self._client.get(f"{key}:failures") or 0)
                return {"open": ttl > 0, "retry_after": max(0, ttl), "failures": failures}
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        now = time.time()
        with self._local_guard:
            failures, open_until = self._local_circuits.get(key, (0, 0))
            if open_until and open_until <= now:
                self._local_circuits.pop(key, None)
                return {"open": False, "retry_after": 0, "failures": 0}
            return {
                "open": open_until > now,
                "retry_after": max(0, int(open_until - now)),
                "failures": failures,
            }

    def record_circuit_result(
        self, key: str, *, ok: bool, failure_threshold: int, cooldown_seconds: int
    ) -> dict:
        failure_threshold, cooldown_seconds = max(1, failure_threshold), max(1, cooldown_seconds)
        if self._client is not None:
            try:
                if ok:
                    self._client.delete(f"{key}:failures", f"{key}:open")
                else:
                    failures = int(self._client.incr(f"{key}:failures"))
                    self._client.expire(f"{key}:failures", cooldown_seconds)
                    if failures >= failure_threshold:
                        self._client.setex(f"{key}:open", cooldown_seconds, "1")
                return self.circuit_status(key)
            except Exception as exc:  # pragma: no cover - external service
                self._fail(exc)
        now = time.time()
        with self._local_guard:
            if ok:
                self._local_circuits.pop(key, None)
            else:
                failures, open_until = self._local_circuits.get(key, (0, 0))
                failures = failures + 1 if not open_until or open_until >= now else 1
                open_until = now + cooldown_seconds if failures >= failure_threshold else 0
                self._local_circuits[key] = (failures, open_until)
            return self.circuit_status(key)

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
