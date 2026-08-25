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


def client_payload(client: LLMClient) -> dict:
    """Return browser-safe settings without exposing credentials."""
    connections = {}
    for connection_id, connection in client.connections.items():
        api_key = str(connection.get("api_key") or "")
        connections[connection_id] = {
            "name": connection.get("name") or connection_id,
            "base_url": connection.get("base_url") or "",
            "model": connection.get("model") or "",
            "key_configured": bool(api_key),
            "masked_key": mask_key(api_key),
        }
    calls = list(client.call_history)
    prompt_tokens = sum(call["prompt_tokens"] for call in calls)
    completion_tokens = sum(call["completion_tokens"] for call in calls)
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
        "agent_routes": dict(client.agent_routes),
        "agent_catalog": AGENT_CATALOG,
        "diagnostics": {
            "calls": len(calls),
            "successful_calls": sum(1 for call in calls if call["ok"]),
            "failed_calls": sum(1 for call in calls if not call["ok"]),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "average_latency_ms": round(
                sum(call["latency_ms"] for call in calls) / len(calls)
            ) if calls else 0,
            "recent_calls": calls[-12:][::-1],
        },
    }


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
            agent_routes=routes,
        )
        client.call_history.extend(current.call_history)
        return client

    strong_url, strong_model, strong_key = _role_settings(
        payload.get("strong"),
        current_url=current.strong_base_url,
        current_model=current.strong_model,
        current_key=current.strong_api_key,
    )
    cheap_url, cheap_model, cheap_key = _role_settings(
        payload.get("cheap"),
        current_url=current.cheap_base_url,
        current_model=current.cheap_model,
        current_key=current.cheap_api_key,
    )
    client = LLMClient(
        mode=mode,
        strong_model=strong_model,
        cheap_model=cheap_model,
        strong_base_url=strong_url,
        strong_api_key=strong_key,
        cheap_base_url=cheap_url,
        cheap_api_key=cheap_key,
    )
    client.call_history.extend(current.call_history)
    return client
