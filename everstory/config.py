"""Runtime configuration from environment variables (loaded from .env)."""

from __future__ import annotations

import os


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

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Strong role: intent parsing + consistency judging.
LLM_STRONG_BASE_URL = env("LLM_STRONG_BASE_URL", env("LLM_BASE_URL", DEFAULT_BASE_URL))
LLM_STRONG_API_KEY = env("LLM_STRONG_API_KEY", env("LLM_API_KEY", ""))
LLM_STRONG_MODEL = env("LLM_STRONG_MODEL", env("LLM_MODEL_STRONG", "qwen-plus"))

# Cheap role: narration.
LLM_CHEAP_BASE_URL = env("LLM_CHEAP_BASE_URL", env("LLM_BASE_URL", DEFAULT_BASE_URL))
LLM_CHEAP_API_KEY = env("LLM_CHEAP_API_KEY", env("LLM_API_KEY", ""))
LLM_CHEAP_MODEL = env("LLM_CHEAP_MODEL", env("LLM_MODEL_CHEAP", "qwen-turbo"))


def build_client(mode: str | None = None):
    """A client with the strong and cheap roles possibly routed to different
    vendors. Each role has its own URL, API key, and model name."""
    from .llm.client import LLMClient

    strong_url = env("LLM_STRONG_BASE_URL", env("LLM_BASE_URL", DEFAULT_BASE_URL))
    strong_key = env("LLM_STRONG_API_KEY", env("LLM_API_KEY", ""))
    strong_model = env("LLM_STRONG_MODEL", env("LLM_MODEL_STRONG", "qwen-plus"))
    cheap_url = env("LLM_CHEAP_BASE_URL", env("LLM_BASE_URL", DEFAULT_BASE_URL))
    cheap_key = env("LLM_CHEAP_API_KEY", env("LLM_API_KEY", ""))
    cheap_model = env("LLM_CHEAP_MODEL", env("LLM_MODEL_CHEAP", "qwen-turbo"))
    return LLMClient(
        mode=mode or env("LLM_MODE", "stub"),
        base_url=strong_url,
        api_key=strong_key,
        strong_model=strong_model,
        cheap_model=cheap_model,
        strong_base_url=strong_url,
        strong_api_key=strong_key,
        cheap_base_url=cheap_url,
        cheap_api_key=cheap_key,
    )
