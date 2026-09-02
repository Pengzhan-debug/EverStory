"""Shared platform-model budget and circuit-breaker guardrails."""

from __future__ import annotations

import os
from datetime import datetime, timezone


class GuardrailBlocked(RuntimeError):
    """Raised before a provider call when a shared safety limit is active."""


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class PlatformGuardrails:
    def __init__(
        self,
        runtime,
        user_id: str,
        *,
        daily_token_limit: int = 0,
        reservation_tokens: int = 2048,
        failure_threshold: int = 3,
        cooldown_seconds: int = 300,
    ) -> None:
        self.runtime = runtime
        self.user_id = user_id
        self.daily_token_limit = max(0, daily_token_limit)
        self.reservation_tokens = max(1, reservation_tokens)
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1, cooldown_seconds)

    @classmethod
    def from_env(cls, runtime, user_id: str) -> "PlatformGuardrails":
        return cls(
            runtime,
            user_id,
            daily_token_limit=_env_int("PLATFORM_ACCOUNT_DAILY_TOKEN_LIMIT", 0),
            reservation_tokens=_env_int("PLATFORM_TOKEN_RESERVATION", 2048),
            failure_threshold=_env_int("PLATFORM_CIRCUIT_FAILURE_THRESHOLD", 3),
            cooldown_seconds=_env_int("PLATFORM_CIRCUIT_COOLDOWN_SECONDS", 300),
        )

    def _budget_scope(self) -> tuple[str, int]:
        now = datetime.now(timezone.utc)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() + 86400
        ttl = max(60, int(tomorrow - now.timestamp()) + 60)
        return f"platform-budget:{self.user_id}:{now:%Y-%m-%d}", ttl

    def _circuit_scope(self, connection_id: str) -> str:
        return f"platform-circuit:{connection_id}"

    def begin(self, connection_id: str, estimated_tokens: int = 0) -> dict:
        circuit = self.runtime.circuit_status(self._circuit_scope(connection_id))
        if circuit["open"]:
            raise GuardrailBlocked(
                "Platform model circuit is cooling down after repeated provider failures."
            )
        reserved = 0
        if self.daily_token_limit:
            budget_key, ttl = self._budget_scope()
            reserved = min(
                max(self.reservation_tokens, int(estimated_tokens)),
                self.daily_token_limit,
            )
            allowed, used = self.runtime.reserve_tokens(
                budget_key, self.daily_token_limit, reserved, ttl
            )
            if not allowed:
                raise GuardrailBlocked(
                    "Platform daily token budget exhausted for this account. "
                    "Use a personal API connection or try again tomorrow."
                )
            return {"budget_key": budget_key, "ttl": ttl, "reserved": reserved, "used": used}
        return {"budget_key": "", "ttl": 0, "reserved": 0, "used": 0}

    def finish(self, connection_id: str, reservation: dict, *, ok: bool, tokens: int) -> None:
        reserved = int(reservation.get("reserved") or 0)
        budget_key = str(reservation.get("budget_key") or "")
        if budget_key and reserved:
            actual = max(0, int(tokens)) if ok else 0
            self.runtime.adjust_tokens(
                budget_key,
                actual - reserved,
                int(reservation.get("ttl") or 60),
            )
        self.runtime.record_circuit_result(
            self._circuit_scope(connection_id),
            ok=ok,
            failure_threshold=self.failure_threshold,
            cooldown_seconds=self.cooldown_seconds,
        )

    def status(self, connection_ids=()) -> dict:
        budget_key, _ = self._budget_scope()
        used = self.runtime.counter_value(budget_key) if self.daily_token_limit else 0
        circuits = {
            str(connection_id): self.runtime.circuit_status(
                self._circuit_scope(str(connection_id))
            )
            for connection_id in connection_ids
        }
        return {
            "daily_token_limit": self.daily_token_limit,
            "daily_tokens_used": used,
            "daily_tokens_remaining": (
                max(0, self.daily_token_limit - used) if self.daily_token_limit else None
            ),
            "reservation_tokens": self.reservation_tokens,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "open_circuits": sum(1 for state in circuits.values() if state["open"]),
            "circuits": circuits,
        }
