"""Provider-agnostic LLM client (OpenAI-compatible chat completions).

Two modes:
- ``stub`` (default): deterministic, offline, test-friendly.
- ``api``: calls any OpenAI-compatible endpoint (Qwen, DeepSeek, ...).
"""

from __future__ import annotations

import time
import json
import uuid
from collections import deque
from datetime import datetime, timezone

from ..config import (
    LLM_CHEAP_API_KEY,
    LLM_CHEAP_BASE_URL,
    LLM_CHEAP_MODEL,
    LLM_MODE,
    LLM_STRONG_API_KEY,
    LLM_STRONG_BASE_URL,
    LLM_STRONG_MODEL,
    PLATFORM_SESSION_TOKEN_LIMIT,
)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        mode: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        strong_model: str | None = None,
        cheap_model: str | None = None,
        strong_base_url: str | None = None,
        strong_api_key: str | None = None,
        cheap_base_url: str | None = None,
        cheap_api_key: str | None = None,
        connections: dict[str, dict] | None = None,
        platform_catalog: dict[str, dict] | None = None,
        agent_routes: dict[str, str] | None = None,
        platform_token_limit: int | None = None,
        platform_guard=None,
        default_credential_source: str = "platform",
    ) -> None:
        self.mode = (mode or LLM_MODE).lower()
        self.base_url = base_url or LLM_STRONG_BASE_URL
        self.api_key = api_key or LLM_STRONG_API_KEY
        self.strong_model = strong_model or LLM_STRONG_MODEL
        self.cheap_model = cheap_model or LLM_CHEAP_MODEL
        # The strong and cheap roles can route to *different* vendors.
        self.strong_base_url = (strong_base_url or self.base_url).rstrip("/")
        self.strong_api_key = strong_api_key or self.api_key
        self.cheap_base_url = (cheap_base_url or self.base_url).rstrip("/")
        self.cheap_api_key = cheap_api_key or self.api_key
        raw_connections = connections or {
            "reasoning": {
                "name": "Reasoning API",
                "base_url": self.strong_base_url,
                "api_key": self.strong_api_key,
                "model": self.strong_model,
                "credential_source": default_credential_source,
            },
            "story": {
                "name": "Story API",
                "base_url": self.cheap_base_url,
                "api_key": self.cheap_api_key,
                "model": self.cheap_model,
                "credential_source": default_credential_source,
            },
        }
        self.connections = {
            connection_id: {
                **connection,
                "credential_source": (
                    connection.get("credential_source")
                    or connection.get("source")
                    or (default_credential_source if connections is None else "personal")
                ),
                "input_cost_per_million": float(
                    connection.get("input_cost_per_million") or 0
                ),
                "output_cost_per_million": float(
                    connection.get("output_cost_per_million") or 0
                ),
            }
            for connection_id, connection in raw_connections.items()
        }
        raw_catalog = platform_catalog or {
            connection_id: connection
            for connection_id, connection in self.connections.items()
            if str(connection.get("credential_source") or default_credential_source).lower()
            == "platform"
        }
        # The catalog keeps hosted models available for session-scoped
        # activation without ever sending their credentials to the browser.
        self.platform_catalog = {
            connection_id: dict(connection)
            for connection_id, connection in raw_catalog.items()
        }
        self.agent_routes = agent_routes or {
            "intent_parser": "reasoning",
            "consistency_judge": "reasoning",
            "case_director": "reasoning",
            "case_analyst": "reasoning",
            "skeptic": "reasoning",
            "narrator": "story",
            "npc_dialogue": "story",
            "field_investigator": "story",
        }
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.call_history = deque(maxlen=2000)
        self.platform_token_limit = (
            PLATFORM_SESSION_TOKEN_LIMIT
            if platform_token_limit is None
            else max(0, int(platform_token_limit))
        )
        self._platform_tokens_consumed = 0
        self.platform_guard = platform_guard
        # A personal route never falls through to a hosted credential. Retried
        # calls stay on the same resolved endpoint and key.
        self.allow_platform_fallback = False
        self.stub_responder = None

    def resolve_route(
        self,
        *,
        agent: str | None = None,
        role: str | None = None,
        model: str | None = None,
        connection_id: str | None = None,
    ) -> tuple[str, str, str, str]:
        """Resolve one call to (connection id, URL, key, model)."""
        route_id = connection_id or (self.agent_routes.get(agent) if agent else None)
        connection = self.connections.get(route_id or "")
        if connection is not None:
            return (
                route_id or "",
                str(connection["base_url"]).rstrip("/"),
                str(connection.get("api_key") or ""),
                str(connection.get("model") or model or self.cheap_model),
            )
        if route_id:
            raise LLMError(f"Unknown model connection '{route_id}'.")
        if role == "strong" or (role is None and model == self.strong_model):
            return "reasoning", self.strong_base_url, self.strong_api_key, model or self.strong_model
        return "story", self.cheap_base_url, self.cheap_api_key, model or self.cheap_model

    def credential_source(self, connection_id: str) -> str:
        source = str(
            self.connections.get(connection_id, {}).get("credential_source")
            or "personal"
        ).lower()
        return source if source in {"platform", "personal"} else "personal"

    def platform_tokens_used(self) -> int:
        history_total = sum(
            int(call.get("prompt_tokens", 0)) + int(call.get("completion_tokens", 0))
            for call in self.call_history
            if call.get("credential_source") == "platform" and call.get("ok")
        )
        return max(int(getattr(self, "_platform_tokens_consumed", 0)), history_total)

    def _ensure_platform_quota(self, connection_id: str) -> None:
        if self.credential_source(connection_id) != "platform":
            return
        if self.platform_token_limit and self.platform_tokens_used() >= self.platform_token_limit:
            raise LLMError(
                "Platform token allowance exhausted for this session. "
                "Add a personal API connection or try again after the session resets."
            )

    def _begin_platform_request(self, connection_id: str, messages: list[dict]):
        self._ensure_platform_quota(connection_id)
        if self.credential_source(connection_id) != "platform" or self.platform_guard is None:
            return None
        try:
            # Character count is intentionally conservative for mixed Chinese/
            # English prompts. The configured reservation is also the maximum
            # completion size sent to hosted models.
            prompt_estimate = max(
                1,
                sum(len(str(message.get("content") or "")) for message in messages),
            )
            return self.platform_guard.begin(
                connection_id,
                prompt_estimate + int(self.platform_guard.reservation_tokens),
            )
        except RuntimeError as exc:
            raise LLMError(str(exc)) from exc

    def _finish_platform_request(
        self, connection_id: str, reservation, *, ok: bool
    ) -> None:
        if reservation is None or self.platform_guard is None:
            return
        tokens = int(self.last_usage.get("prompt_tokens", 0)) + int(
            self.last_usage.get("completion_tokens", 0)
        )
        self.platform_guard.finish(connection_id, reservation, ok=ok, tokens=tokens)

    def _record_call(
        self,
        *,
        agent: str | None,
        connection_id: str,
        model: str,
        latency_ms: int,
        ok: bool,
        error: str = "",
    ) -> None:
        connection = self.connections.get(connection_id, {})
        prompt_tokens = int(self.last_usage.get("prompt_tokens", 0))
        completion_tokens = int(self.last_usage.get("completion_tokens", 0))
        estimated_cost = (
            prompt_tokens * float(connection.get("input_cost_per_million") or 0)
            + completion_tokens * float(connection.get("output_cost_per_million") or 0)
        ) / 1_000_000
        source = self.credential_source(connection_id)
        if ok and source == "platform":
            self._platform_tokens_consumed = int(
                getattr(self, "_platform_tokens_consumed", 0)
            ) + prompt_tokens + completion_tokens
        self.call_history.append(
            {
                "id": uuid.uuid4().hex,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "agent": agent or "unassigned",
                "connection_id": connection_id,
                "credential_source": source,
                "model": model,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "estimated_cost_usd": round(estimated_cost, 8),
                "ok": ok,
                "error": error[:160],
            }
        )

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        role: str | None = None,
        agent: str | None = None,
        connection_id: str | None = None,
    ) -> str:
        _, _, _, model = self.resolve_route(
            agent=agent, role=role, model=model, connection_id=connection_id
        )
        if self.mode == "stub":
            if self.stub_responder is not None:
                return self.stub_responder(messages, model, json_mode)
            # Short fixed reply: echoing the prompt back would let baselines
            # grow context recursively and make stub evals quadratic.
            return "[stub] ok"
        return self._chat_api(
            messages,
            model,
            json_mode,
            temperature,
            role=role,
            agent=agent,
            connection_id=connection_id,
        )

    def _chat_api(
        self,
        messages: list[dict],
        model: str,
        json_mode: bool,
        temperature: float,
        role: str | None = None,
        agent: str | None = None,
        connection_id: str | None = None,
    ) -> str:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise LLMError("requests is required for LLM API mode") from exc
        route_id, base_url, api_key, model = self.resolve_route(
            agent=agent, role=role, model=model, connection_id=connection_id
        )
        try:
            reservation = self._begin_platform_request(route_id, messages)
        except LLMError as exc:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent,
                connection_id=route_id,
                model=model,
                latency_ms=0,
                ok=False,
                error=str(exc),
            )
            raise
        url = base_url + "/chat/completions"
        if not api_key:
            error = f"API key is not set for model '{model}' (or use LLM_MODE=stub)"
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent, connection_id=route_id, model=model,
                latency_ms=0, ok=False, error=error,
            )
            self._finish_platform_request(route_id, reservation, ok=False)
            raise LLMError(error)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if reservation is not None:
            payload["max_tokens"] = int(self.platform_guard.reservation_tokens)
        last_error: Exception | None = None
        started = time.perf_counter()
        for attempt in range(3):  # transient network failures are common
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=120,
                )
                if resp.status_code == 200:
                    break
                if resp.status_code < 500 and resp.status_code != 429:
                    self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    self._record_call(
                        agent=agent,
                        connection_id=route_id,
                        model=model,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        ok=False,
                        error=f"HTTP {resp.status_code}: {resp.text[:120]}",
                    )
                    self._finish_platform_request(route_id, reservation, ok=False)
                    raise LLMError(
                        f"LLM API error {resp.status_code}: {resp.text[:300]}"
                    )
                last_error = LLMError(
                    f"LLM API error {resp.status_code}: {resp.text[:200]}"
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
            time.sleep(2 * (attempt + 1))
        else:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent,
                connection_id=route_id,
                model=model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                ok=False,
                error=str(last_error),
            )
            self._finish_platform_request(route_id, reservation, ok=False)
            raise LLMError(f"LLM API request failed after retries: {last_error}") from last_error
        if resp.status_code != 200:
            raise LLMError(f"LLM API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
        self._record_call(
            agent=agent,
            connection_id=route_id,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            ok=True,
        )
        self._finish_platform_request(route_id, reservation, ok=True)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover
            raise LLMError(f"Unexpected LLM response: {str(data)[:300]}") from exc

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        role: str | None = None,
        agent: str | None = None,
        connection_id: str | None = None,
    ):
        """Stream a chat completion token-by-token (OpenAI-compatible SSE)."""
        model = model or self.cheap_model
        if self.mode == "stub":
            yield self.chat(
                messages,
                model=model,
                json_mode=json_mode,
                temperature=temperature,
                role=role,
                agent=agent,
                connection_id=connection_id,
            )
            return
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise LLMError("requests is required for LLM API mode") from exc
        route_id, base_url, api_key, model = self.resolve_route(
            agent=agent, role=role, model=model, connection_id=connection_id
        )
        try:
            reservation = self._begin_platform_request(route_id, messages)
        except LLMError as exc:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent,
                connection_id=route_id,
                model=model,
                latency_ms=0,
                ok=False,
                error=str(exc),
            )
            raise
        url = base_url + "/chat/completions"
        if not api_key:
            error = f"API key is not set for model '{model}' (or use LLM_MODE=stub)"
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent, connection_id=route_id, model=model,
                latency_ms=0, ok=False, error=error,
            )
            self._finish_platform_request(route_id, reservation, ok=False)
            raise LLMError(error)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if reservation is not None:
            payload["max_tokens"] = int(self.platform_guard.reservation_tokens)
        last_error: Exception | None = None
        started = time.perf_counter()
        resp = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    stream=True,
                    timeout=120,
                )
                if resp.status_code == 200:
                    break
                if resp.status_code < 500 and resp.status_code != 429:
                    self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    self._record_call(
                        agent=agent,
                        connection_id=route_id,
                        model=model,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        ok=False,
                        error=f"HTTP {resp.status_code}: {resp.text[:120]}",
                    )
                    self._finish_platform_request(route_id, reservation, ok=False)
                    raise LLMError(
                        f"LLM API error {resp.status_code}: {resp.text[:300]}"
                    )
                last_error = LLMError(
                    f"LLM API error {resp.status_code}: {resp.text[:200]}"
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
            time.sleep(2 * (attempt + 1))
        else:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
            self._record_call(
                agent=agent,
                connection_id=route_id,
                model=model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                ok=False,
                error=str(last_error),
            )
            self._finish_platform_request(route_id, reservation, ok=False)
            raise LLMError(f"LLM API request failed after retries: {last_error}") from last_error
        if resp is None or resp.status_code != 200:
            raise LLMError(f"LLM API error: {resp.status_code if resp else 'no response'}")
        prompt_tokens = 0
        completion_tokens = 0
        try:
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                data_str = raw[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    usage = chunk.get("usage") or {}
                    if usage.get("prompt_tokens"):
                        prompt_tokens = int(usage["prompt_tokens"])
                    if usage.get("completion_tokens"):
                        completion_tokens = int(usage["completion_tokens"])
                    delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        finally:
            resp.close()
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
            self._record_call(
                agent=agent,
                connection_id=route_id,
                model=model,
                latency_ms=round((time.perf_counter() - started) * 1000),
                ok=True,
            )
            self._finish_platform_request(route_id, reservation, ok=True)
