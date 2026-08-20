"""Runtime configuration from environment variables."""

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
LLM_BASE_URL = env(
    "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "qwen-plus")
LLM_MODEL_CHEAP = env("LLM_MODEL_CHEAP", "qwen-turbo")
