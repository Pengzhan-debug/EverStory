"""Provider-agnostic LLM client (OpenAI-compatible chat completions).

Two modes:
- ``stub`` (default): deterministic, offline, test-friendly.
- ``api``: calls any OpenAI-compatible endpoint (Qwen, DeepSeek, ...).
"""

from __future__ import annotations

from ..config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODE,
    LLM_MODEL_CHEAP,
    LLM_MODEL_STRONG,
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
    ) -> None:
        self.mode = (mode or LLM_MODE).lower()
        self.base_url = base_url or LLM_BASE_URL
        self.api_key = api_key or LLM_API_KEY
        self.strong_model = strong_model or LLM_MODEL_STRONG
        self.cheap_model = cheap_model or LLM_MODEL_CHEAP
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
            last = messages[-1]["content"] if messages else ""
            return f"[stub:{model}] {last}"
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
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not set (or use LLM_MODE=stub)")
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
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
