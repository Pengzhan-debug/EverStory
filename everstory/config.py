"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader (stdlib only). Existing environment variables win."""
    path = path or os.path.join(os.getcwd(), ".env")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


LLM_MODE = env("LLM_MODE", "stub")  # stub | api
LLM_BASE_URL = env(
    "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "qwen-plus")
LLM_MODEL_CHEAP = env("LLM_MODEL_CHEAP", "qwen-turbo")


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    strong_model: str
    cheap_model: str


def load_providers() -> list[Provider]:
    """Providers for cross-vendor benchmarking.

    Configure several providers in ``.env`` with prefixed variables::

        LLM_PROVIDERS=qwen,deepseek
        LLM_PROVIDER_QWEN_BASE_URL=...
        LLM_PROVIDER_QWEN_API_KEY=...
        LLM_PROVIDER_QWEN_STRONG_MODEL=...
        LLM_PROVIDER_QWEN_CHEAP_MODEL=...

    Falls back to the legacy single-provider variables as provider "default".
    """
    names = [n.strip() for n in env("LLM_PROVIDERS", "").split(",") if n.strip()]
    providers: list[Provider] = []
    for name in names:
        prefix = f"LLM_PROVIDER_{name.upper()}"
        providers.append(
            Provider(
                name=name,
                base_url=env(f"{prefix}_BASE_URL", LLM_BASE_URL),
                api_key=env(f"{prefix}_API_KEY", LLM_API_KEY),
                strong_model=env(f"{prefix}_STRONG_MODEL", LLM_MODEL_STRONG),
                cheap_model=env(f"{prefix}_CHEAP_MODEL", LLM_MODEL_CHEAP),
            )
        )
    if not providers:
        providers.append(
            Provider(
                name="default",
                base_url=LLM_BASE_URL,
                api_key=LLM_API_KEY,
                strong_model=LLM_MODEL_STRONG,
                cheap_model=LLM_MODEL_CHEAP,
            )
        )
    return providers


def build_role_client(mode: str | None = None) -> "LLMClient":
    """Client with the strong and cheap roles possibly routed to different
    vendors, configured by ``LLM_ROLE_STRONG`` / ``LLM_ROLE_CHEAP`` (names
    must match entries in ``LLM_PROVIDERS``). Falls back to the first provider
    for both roles."""
    from .llm.client import LLMClient

    providers = load_providers()
    by_name = {p.name: p for p in providers}
    strong = by_name.get(env("LLM_ROLE_STRONG", ""), providers[0])
    cheap = by_name.get(env("LLM_ROLE_CHEAP", ""), providers[0])
    return LLMClient(
        mode=mode or LLM_MODE,
        base_url=strong.base_url,
        api_key=strong.api_key,
        strong_model=strong.strong_model,
        cheap_model=cheap.cheap_model,
        strong_base_url=strong.base_url,
        strong_api_key=strong.api_key,
        cheap_base_url=cheap.base_url,
        cheap_api_key=cheap.api_key,
    )
