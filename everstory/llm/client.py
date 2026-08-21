"""Provider-agnostic LLM client (OpenAI-compatible chat completions).

Two modes:
- ``stub`` (default): deterministic, offline, test-friendly.
- ``api``: calls any OpenAI-compatible endpoint (Qwen, DeepSeek, ...).
"""

from __future__ import annotations

import time

from ..config import (
    LLM_CHEAP_API_KEY,
    LLM_CHEAP_BASE_URL,
    LLM_CHEAP_MODEL,
    LLM_MODE,
    LLM_STRONG_API_KEY,
    LLM_STRONG_BASE_URL,
    LLM_STRONG_MODEL,
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
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.stub_responder = None

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> str:
        model = model or self.cheap_model
        if self.mode == "stub":
            if self.stub_responder is not None:
                return self.stub_responder(messages, model, json_mode)
            # Short fixed reply: echoing the prompt back would let baselines
            # grow context recursively and make stub evals quadratic.
            return "[stub] ok"
        return self._chat_api(messages, model, json_mode, temperature)

    def _chat_api(
        self,
        messages: list[dict],
        model: str,
        json_mode: bool,
        temperature: float,
    ) -> str:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise LLMError("requests is required for LLM API mode") from exc
        if model == self.strong_model:
            url = self.strong_base_url + "/chat/completions"
            api_key = self.strong_api_key
        else:
            url = self.cheap_base_url + "/chat/completions"
            api_key = self.cheap_api_key
        if not api_key:
            raise LLMError(f"API key is not set for model '{model}' (or use LLM_MODE=stub)")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        last_error: Exception | None = None
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
            raise LLMError(f"LLM API request failed after retries: {last_error}") from last_error
        if resp.status_code != 200:
            raise LLMError(f"LLM API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover
            raise LLMError(f"Unexpected LLM response: {str(data)[:300]}") from exc
