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
# Render and similar hosts expose encrypted secret files under /etc/secrets.
# Existing process environment values still win, so Blueprint-managed values
# cannot be silently overridden by the file.
_load_dotenv(os.environ.get("EVERSTORY_SECRET_FILE", "/etc/secrets/everstory.env"))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_float(name: str, default: float = 0) -> float:
    try:
        return max(0, float(env(name, str(default))))
    except ValueError:
        return default


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

ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_MODEL_CONNECTIONS = {
    "ark_kimi_k27_code": (
        "Kimi K2.7 Code", "kimi-k2.7-code", "ARK_KIMI_K27_CODE_API_KEY", "long_context"
    ),
    "ark_deepseek_v4_pro": (
        "DeepSeek V4 Pro", "deepseek-v4-pro", "ARK_DEEPSEEK_V4_PRO_API_KEY", "reasoning"
    ),
    "ark_deepseek_v4_flash": (
        "DeepSeek V4 Flash", "deepseek-v4-flash", "ARK_DEEPSEEK_V4_FLASH_API_KEY", "fast_reasoning"
    ),
    "ark_glm_53": (
        "GLM 5.3", "glm-5.3", "ARK_GLM_53_API_KEY", "analysis"
    ),
    "ark_minimax_m3": (
        "MiniMax M3", "minimax-m3", "ARK_MINIMAX_M3_API_KEY", "creative"
    ),
    "ark_doubao_seed_20_lite": (
        "Doubao Seed 2.0 Lite", "doubao-seed-2.0-lite", "ARK_DOUBAO_SEED_20_LITE_API_KEY", "low_latency"
    ),
    "ark_doubao_seed_21_turbo": (
        "Doubao Seed 2.1 Turbo", "doubao-seed-2.1-turbo", "ARK_DOUBAO_SEED_21_TURBO_API_KEY", "dialogue"
    ),
}
ARK_AGENT_ROUTES = {
    "case_director": "ark_deepseek_v4_pro",
    "field_investigator": "ark_doubao_seed_20_lite",
    "case_analyst": "ark_glm_53",
    "skeptic": "ark_kimi_k27_code",
    "intent_parser": "ark_doubao_seed_20_lite",
    "consistency_judge": "ark_deepseek_v4_flash",
    "narrator": "ark_minimax_m3",
    "npc_dialogue": "ark_doubao_seed_20_lite",
}

# The hosted/default credential is a convenience allowance, not a shared
# unlimited key.  Each browser runtime receives its own accounting window.
# Set to 0 to disable the limit for private/local deployments.
try:
    PLATFORM_SESSION_TOKEN_LIMIT = max(
        0, int(env("PLATFORM_SESSION_TOKEN_LIMIT", "50000"))
    )
except ValueError:
    PLATFORM_SESSION_TOKEN_LIMIT = 50000


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
    # Coding Plan keys are distinct from generic Volcengine credentials. Do
    # not silently reuse VOLC_API_KEY: a wrong credential would activate seven
    # broken routes and the platform returns AuthenticationError.
    ark_base_url = env("ARK_BASE_URL", ARK_DEFAULT_BASE_URL).rstrip("/")
    ark_model_keys = {
        connection_id: env(api_key_env, "")
        for connection_id, (_, _, api_key_env, _) in ARK_MODEL_CONNECTIONS.items()
    }
    enable_default = "true" if any(ark_model_keys.values()) else "false"
    ark_enabled = env("ARK_ENABLE_CATALOG", enable_default).lower() in {
        "1", "true", "yes", "on"
    }
    connections = {
        "reasoning": {
            "name": "Reasoning API",
            "base_url": strong_url,
            "api_key": strong_key,
            "model": strong_model,
            "credential_source": "platform",
            "input_cost_per_million": env_float("LLM_STRONG_INPUT_COST_PER_MILLION"),
            "output_cost_per_million": env_float("LLM_STRONG_OUTPUT_COST_PER_MILLION"),
        },
        "story": {
            "name": "Story API",
            "base_url": cheap_url,
            "api_key": cheap_key,
            "model": cheap_model,
            "credential_source": "platform",
            "input_cost_per_million": env_float("LLM_CHEAP_INPUT_COST_PER_MILLION"),
            "output_cost_per_million": env_float("LLM_CHEAP_OUTPUT_COST_PER_MILLION"),
        },
    }
    if ark_enabled:
        for connection_id, (name, model, _, capability) in ARK_MODEL_CONNECTIONS.items():
            connections[connection_id] = {
                "name": name,
                "base_url": ark_base_url,
                "api_key": ark_model_keys[connection_id],
                "model": model,
                "credential_source": "platform",
                "provider": "volcengine_ark",
                "capability": capability,
                "input_cost_per_million": 0,
                "output_cost_per_million": 0,
            }
    agent_routes = {
        "intent_parser": "reasoning",
        "consistency_judge": "reasoning",
        "case_director": "reasoning",
        "case_analyst": "reasoning",
        "skeptic": "reasoning",
        "narrator": "story",
        "npc_dialogue": "story",
        "field_investigator": "story",
    }
    if ark_enabled:
        agent_routes.update(
            {
                agent: connection_id
                for agent, connection_id in ARK_AGENT_ROUTES.items()
                if ark_model_keys[connection_id]
            }
        )

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
        connections=connections,
        agent_routes=agent_routes,
        platform_token_limit=PLATFORM_SESSION_TOKEN_LIMIT,
    )
