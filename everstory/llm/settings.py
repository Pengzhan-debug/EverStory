"""Session-scoped LLM connection settings for the web console."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .client import LLMClient


MODEL_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,120}$")
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

AGENT_CATALOG = [
    {"id": "case_director", "name": "Case Director", "group": "Investigation team", "active": True},
    {"id": "field_investigator", "name": "Field Investigator", "group": "Investigation team", "active": True},
    {"id": "case_analyst", "name": "Case Analyst", "group": "Investigation team", "active": True},
    {"id": "skeptic", "name": "Skeptic", "group": "Investigation team", "active": True},
    {"id": "intent_parser", "name": "Intent Parser", "group": "Game runtime", "active": True},
    {"id": "consistency_judge", "name": "Consistency Judge", "group": "Game runtime", "active": True},
    {"id": "narrator", "name": "Narrator", "group": "Game runtime", "active": True},
    {"id": "npc_dialogue", "name": "NPC Dialogue", "group": "Game runtime", "active": True},
]


def mask_key(value: str) -> str:
    if not value:
        return ""
    suffix = value[-4:] if len(value) >= 4 else value
    return f"••••••••{suffix}"


def _connection_payload(client: LLMClient, connection_id: str, connection: dict) -> dict:
    api_key = str(connection.get("api_key") or "")
    source = str(connection.get("credential_source") or "platform").lower()
    return {
        "name": connection.get("name") or connection_id,
        "base_url": connection.get("base_url") or "",
        "model": connection.get("model") or "",
        "provider": connection.get("provider") or "openai_compatible",
        "capability": connection.get("capability") or "general",
        "credential_source": source,
        "editable": source == "personal",
        "input_cost_per_million": float(
            connection.get("input_cost_per_million") or 0
        ),
        "output_cost_per_million": float(
            connection.get("output_cost_per_million") or 0
        ),
        "key_configured": bool(api_key),
        "masked_key": mask_key(api_key) if source == "personal" else "",
    }


def client_payload(client: LLMClient) -> dict:
    """Return browser-safe settings without exposing credentials."""
    connections = {
        connection_id: _connection_payload(client, connection_id, connection)
        for connection_id, connection in client.connections.items()
    }
    platform_catalog = {
        connection_id: _connection_payload(client, connection_id, connection)
        for connection_id, connection in client.platform_catalog.items()
    }
    calls = list(client.call_history)
    platform_ids = [
        connection_id
        for connection_id, connection in client.connections.items()
        if str(connection.get("credential_source") or "personal").lower()
        == "platform"
    ]
    guard = getattr(client, "platform_guard", None)
    guardrail_status = guard.status(platform_ids) if guard is not None else {
        "daily_token_limit": 0,
        "daily_tokens_used": 0,
        "daily_tokens_remaining": None,
        "open_circuits": 0,
        "circuits": {},
    }
    prompt_tokens = sum(int(call.get("prompt_tokens") or 0) for call in calls)
    completion_tokens = sum(int(call.get("completion_tokens") or 0) for call in calls)
    return {
        "mode": client.mode,
        "strong": {
            "base_url": client.strong_base_url,
            "model": client.strong_model,
            "key_configured": bool(client.strong_api_key),
            "masked_key": mask_key(client.strong_api_key),
        },
        "cheap": {
            "base_url": client.cheap_base_url,
            "model": client.cheap_model,
            "key_configured": bool(client.cheap_api_key),
            "masked_key": mask_key(client.cheap_api_key),
        },
        "connections": connections,
        "platform_catalog": platform_catalog,
        "agent_routes": dict(client.agent_routes),
        "agent_catalog": AGENT_CATALOG,
        "credential_policy": {
            "platform_connections_read_only": True,
            "personal_keys_session_only": True,
            "fallback_to_platform": getattr(client, "allow_platform_fallback", False),
            "platform_token_limit": getattr(client, "platform_token_limit", 0),
            "platform_tokens_used": client.platform_tokens_used(),
            "platform_guardrails": guardrail_status,
        },
        "diagnostics": {
            "calls": len(calls),
            "successful_calls": sum(1 for call in calls if call.get("ok")),
            "failed_calls": sum(1 for call in calls if not call.get("ok")),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "average_latency_ms": round(
                sum(int(call.get("latency_ms") or 0) for call in calls) / len(calls)
            ) if calls else 0,
            "recent_calls": calls[-12:][::-1],
        },
    }


def account_profile(client: LLMClient) -> dict:
    """Return the internal account profile; callers must encrypt before storage."""
    personal_connections = {
        connection_id: dict(connection)
        for connection_id, connection in client.connections.items()
        if str(connection.get("credential_source") or "personal").lower()
        == "personal"
    }
    platform_connection_ids = [
        connection_id
        for connection_id, connection in client.connections.items()
        if str(connection.get("credential_source") or "platform").lower()
        == "platform"
    ]
    return {
        "mode": client.mode,
        "platform_connection_ids": platform_connection_ids,
        "personal_connections": personal_connections,
        "agent_routes": dict(client.agent_routes),
    }


def apply_account_profile(current: LLMClient, profile: object) -> LLMClient:
    """Restore an internal profile onto a fresh/current platform catalog."""
    if not isinstance(profile, dict):
        return current
    raw_platform_ids = profile.get("platform_connection_ids")
    platform_ids = raw_platform_ids if isinstance(raw_platform_ids, list) else []
    connections: dict[str, dict] = {}
    for connection_id in platform_ids:
        normalized_id = str(connection_id)
        catalog_connection = current.platform_catalog.get(normalized_id)
        if catalog_connection:
            public_connection = dict(catalog_connection)
            public_connection.pop("api_key", None)
            connections[normalized_id] = public_connection
    raw_personal = profile.get("personal_connections")
    if isinstance(raw_personal, dict):
        for connection_id, connection in raw_personal.items():
            if isinstance(connection, dict):
                connections[str(connection_id)] = dict(connection)
    if not connections:
        return current
    first_connection = next(iter(connections))
    raw_routes = profile.get("agent_routes")
    route_values = raw_routes if isinstance(raw_routes, dict) else {}
    routes = {
        agent["id"]: (
            str(route_values.get(agent["id"]))
            if str(route_values.get(agent["id"]) or "") in connections
            else first_connection
        )
        for agent in AGENT_CATALOG
    }
    return update_client(
        current,
        {
            "mode": profile.get("mode") or current.mode,
            "connections": connections,
            "agent_routes": routes,
        },
    )


def _validated_url(value: object, fallback: str) -> str:
    raw = str(value or fallback).strip().rstrip("/")
    if len(raw) > 500:
        raise ValueError("Base URL is too long.")
    parsed = urlparse(raw)
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Base URL must be an absolute URL without credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL cannot contain a query string or fragment.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS
    ):
        raise ValueError("Use HTTPS, or HTTP only for a local model server.")
    return raw


def _validated_model(value: object, fallback: str) -> str:
    model = str(value or fallback).strip()
    if not MODEL_RE.fullmatch(model):
        raise ValueError("Model name must be 1-120 printable characters.")
    return model


def _validated_rate(value: object, fallback: float = 0) -> float:
    try:
        rate = float(fallback if value is None or value == "" else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Token price must be a number.") from exc
    if rate < 0 or rate > 10000:
        raise ValueError("Token price must be between 0 and 10000 USD per million.")
    return rate


def _role_settings(raw: object, *, current_url: str, current_model: str,
                   current_key: str) -> tuple[str, str, str]:
    data = raw if isinstance(raw, dict) else {}
    base_url = _validated_url(data.get("base_url"), current_url)
    model = _validated_model(data.get("model"), current_model)
    if data.get("clear_key") is True:
        api_key = ""
    else:
        supplied = str(data.get("api_key") or "").strip()
        api_key = supplied or current_key
    if len(api_key) > 4096:
        raise ValueError("API key is too long.")
    return base_url, model, api_key


def update_client(current: LLMClient, payload: object) -> LLMClient:
    if not isinstance(payload, dict):
        raise ValueError("Settings must be a JSON object.")
    mode = str(payload.get("mode") or current.mode).lower().strip()
    if mode not in {"stub", "api"}:
        raise ValueError("Mode must be 'api' or 'stub'.")

    if "connections" in payload:
        raw_connections = payload.get("connections")
        if not isinstance(raw_connections, dict) or not raw_connections:
            raise ValueError("At least one API connection is required.")
        connections: dict[str, dict] = {}
        for connection_id, raw in raw_connections.items():
            if not ID_RE.fullmatch(str(connection_id)):
                raise ValueError(f"Invalid connection id: {connection_id}")
            if not isinstance(raw, dict):
                raise ValueError(f"Connection '{connection_id}' must be an object.")
            existing = current.connections.get(connection_id, {})
            catalog_connection = current.platform_catalog.get(str(connection_id), {})
            if not existing and catalog_connection:
                existing = catalog_connection
            existing_source = str(existing.get("credential_source") or "personal").lower()
            if existing_source == "platform" and existing:
                # Hosted credentials are immutable. The browser may echo their
                # public fields, but it can neither read nor overwrite the key.
                if raw.get("api_key") or raw.get("clear_key") is True:
                    raise ValueError(
                        "Platform credentials cannot be edited. Add a personal connection instead."
                    )
                connections[str(connection_id)] = dict(existing)
                continue
            name = str(raw.get("name") or existing.get("name") or connection_id).strip()
            if not name or len(name) > 80:
                raise ValueError("Connection name must be 1-80 characters.")
            url, model, key = _role_settings(
                raw,
                current_url=str(existing.get("base_url") or current.strong_base_url),
                current_model=str(existing.get("model") or current.strong_model),
                current_key=str(existing.get("api_key") or ""),
            )
            connections[str(connection_id)] = {
                "name": name,
                "base_url": url,
                "model": model,
                "api_key": key,
                "credential_source": "personal",
                "provider": str(
                    raw.get("provider") or existing.get("provider") or "openai_compatible"
                )[:80],
                "input_cost_per_million": _validated_rate(
                    raw.get("input_cost_per_million"),
                    float(existing.get("input_cost_per_million") or 0),
                ),
                "output_cost_per_million": _validated_rate(
                    raw.get("output_cost_per_million"),
                    float(existing.get("output_cost_per_million") or 0),
                ),
            }

        raw_routes = payload.get("agent_routes")
        if not isinstance(raw_routes, dict):
            raw_routes = current.agent_routes
        first_connection = next(iter(connections))
        routes = {}
        for agent in AGENT_CATALOG:
            route_id = str(raw_routes.get(agent["id"]) or first_connection)
            if route_id not in connections:
                raise ValueError(
                    f"Agent '{agent['id']}' references unknown connection '{route_id}'."
                )
            routes[agent["id"]] = route_id

        strong_connection = connections[routes["intent_parser"]]
        cheap_connection = connections[routes["narrator"]]
        client = LLMClient(
            mode=mode,
            strong_model=strong_connection["model"],
            cheap_model=cheap_connection["model"],
            strong_base_url=strong_connection["base_url"],
            strong_api_key=strong_connection["api_key"],
            cheap_base_url=cheap_connection["base_url"],
            cheap_api_key=cheap_connection["api_key"],
            connections=connections,
            platform_catalog=current.platform_catalog,
            agent_routes=routes,
            platform_token_limit=getattr(current, "platform_token_limit", 0),
            platform_guard=getattr(current, "platform_guard", None),
        )
        client.call_history.extend(current.call_history)
        client._platform_tokens_consumed = current.platform_tokens_used()
        return client

    strong_raw = payload.get("strong")
    cheap_raw = payload.get("cheap")
    strong_route = current.agent_routes.get("intent_parser", "reasoning")
    cheap_route = current.agent_routes.get("narrator", "story")
    strong_current_source = current.credential_source(strong_route)
    cheap_current_source = current.credential_source(cheap_route)
    strong_url, strong_model, strong_key = _role_settings(
        strong_raw,
        current_url=current.strong_base_url,
        current_model=current.strong_model,
        current_key=(
            "" if isinstance(strong_raw, dict) and strong_current_source == "platform"
            else current.strong_api_key
        ),
    )
    cheap_url, cheap_model, cheap_key = _role_settings(
        cheap_raw,
        current_url=current.cheap_base_url,
        current_model=current.cheap_model,
        current_key=(
            "" if isinstance(cheap_raw, dict) and cheap_current_source == "platform"
            else current.cheap_api_key
        ),
    )
    strong_source = "personal" if isinstance(strong_raw, dict) else strong_current_source
    cheap_source = "personal" if isinstance(cheap_raw, dict) else cheap_current_source
    legacy_connections = {
        "reasoning": {
            "name": "Reasoning API", "base_url": strong_url,
            "model": strong_model, "api_key": strong_key,
            "credential_source": strong_source,
        },
        "story": {
            "name": "Story API", "base_url": cheap_url,
            "model": cheap_model, "api_key": cheap_key,
            "credential_source": cheap_source,
        },
    }
    client = LLMClient(
        mode=mode,
        strong_model=strong_model,
        cheap_model=cheap_model,
        strong_base_url=strong_url,
        strong_api_key=strong_key,
        cheap_base_url=cheap_url,
        cheap_api_key=cheap_key,
        connections=legacy_connections,
        platform_catalog=current.platform_catalog,
        platform_token_limit=getattr(current, "platform_token_limit", 0),
        platform_guard=getattr(current, "platform_guard", None),
    )
    client.call_history.extend(current.call_history)
    client._platform_tokens_consumed = current.platform_tokens_used()
    return client
