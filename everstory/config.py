"""Runtime configuration from environment variables."""

from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


LLM_MODE = env("LLM_MODE", "stub")  # stub | api
LLM_BASE_URL = env(
    "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "qwen-plus")
LLM_MODEL_CHEAP = env("LLM_MODEL_CHEAP", "qwen-turbo")
