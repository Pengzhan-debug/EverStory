"""Session-scoped LLM usage aggregation for the model console."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .client import LLMClient


RANGE_CONFIG = {
    "24h": (timedelta(hours=24), "hour", 24),
    "7d": (timedelta(days=7), "day", 7),
    "30d": (timedelta(days=30), "day", 30),
}
METRICS = {"tokens", "requests", "cost", "latency"}
GROUPS = {"source", "agent", "model", "connection"}


def _call_time(call: dict, fallback: datetime) -> datetime:
    raw = call.get("created_at")
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback


def _group_id(call: dict, group_by: str) -> str:
    if group_by == "source":
        return str(call.get("credential_source") or "personal")
    if group_by == "connection":
        return str(call.get("connection_id") or "unassigned")
    return str(call.get(group_by) or "unassigned")


def _value(call: dict, metric: str) -> float:
    if metric == "requests":
        return 1
    if metric == "cost":
        return float(call.get("estimated_cost_usd") or 0)
    if metric == "latency":
        return float(call.get("latency_ms") or 0)
    return int(call.get("total_tokens") or 0) or (
        int(call.get("prompt_tokens") or 0)
        + int(call.get("completion_tokens") or 0)
    )


def usage_payload(
    client: LLMClient,
    *,
    range_key: str = "7d",
    metric: str = "tokens",
    group_by: str = "source",
) -> dict:
    """Aggregate one session's calls into chart-ready, browser-safe data."""
    if range_key not in RANGE_CONFIG:
        raise ValueError("Range must be one of: 24h, 7d, 30d.")
    if metric not in METRICS:
        raise ValueError("Metric must be one of: tokens, requests, cost, latency.")
    if group_by not in GROUPS:
        raise ValueError("Group must be one of: source, agent, model, connection.")

    now = datetime.now(timezone.utc)
    window, unit, count = RANGE_CONFIG[range_key]
    start = now - window
    calls = [
        {**call, "_at": _call_time(call, now)}
        for call in client.call_history
        if _call_time(call, now) >= start
    ]

    prompt_tokens = sum(int(call.get("prompt_tokens") or 0) for call in calls)
    completion_tokens = sum(int(call.get("completion_tokens") or 0) for call in calls)
    total_cost = sum(float(call.get("estimated_cost_usd") or 0) for call in calls)
    successful = sum(1 for call in calls if call.get("ok"))
    platform_used_in_range = sum(
        int(call.get("total_tokens") or 0)
        or int(call.get("prompt_tokens") or 0) + int(call.get("completion_tokens") or 0)
        for call in calls
        if call.get("credential_source") == "platform" and call.get("ok")
    )
    personal_tokens = sum(
        int(call.get("total_tokens") or 0)
        or int(call.get("prompt_tokens") or 0) + int(call.get("completion_tokens") or 0)
        for call in calls
        if call.get("credential_source") != "platform" and call.get("ok")
    )
    limit = getattr(client, "platform_token_limit", 0)
    platform_used = client.platform_tokens_used()
    remaining = max(0, limit - platform_used) if limit else None

    buckets = []
    bucket_lookup = {}
    for offset in range(count):
        if unit == "hour":
            point = (now - timedelta(hours=count - 1 - offset)).replace(
                minute=0, second=0, microsecond=0
            )
            key = point.strftime("%Y-%m-%dT%H:00Z")
            label = point.strftime("%H:00")
        else:
            point = (now - timedelta(days=count - 1 - offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            key = point.strftime("%Y-%m-%d")
            label = point.strftime("%m-%d")
        row = {"key": key, "label": label, "values": {}}
        buckets.append(row)
        bucket_lookup[key] = row

    latency_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    group_totals: dict[str, float] = defaultdict(float)
    for call in calls:
        at = call["_at"]
        bucket_key = (
            at.strftime("%Y-%m-%dT%H:00Z") if unit == "hour" else at.strftime("%Y-%m-%d")
        )
        row = bucket_lookup.get(bucket_key)
        if row is None:
            continue
        group = _group_id(call, group_by)
        value = _value(call, metric)
        if metric == "latency":
            latency_values[(bucket_key, group)].append(value)
        else:
            row["values"][group] = row["values"].get(group, 0) + value
            group_totals[group] += value
    if metric == "latency":
        for (bucket_key, group), values in latency_values.items():
            average = round(sum(values) / len(values), 2)
            bucket_lookup[bucket_key]["values"][group] = average
            group_totals[group] += average

    groups = [
        {"id": group, "total": round(total, 8)}
        for group, total in sorted(group_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    safe_logs = []
    for call in reversed(calls[-100:]):
        safe_logs.append({key: value for key, value in call.items() if key != "_at"})

    return {
        "range": range_key,
        "metric": metric,
        "group_by": group_by,
        "summary": {
            "calls": len(calls),
            "successful_calls": successful,
            "failed_calls": len(calls) - successful,
            "success_rate": round(successful / len(calls) * 100, 1) if calls else 100.0,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "personal_tokens": personal_tokens,
            "platform_tokens": platform_used_in_range,
            "estimated_cost_usd": round(total_cost, 6),
            "average_latency_ms": round(
                sum(int(call.get("latency_ms") or 0) for call in calls) / len(calls)
            ) if calls else 0,
            "platform_quota": {
                "limit": limit,
                "used": platform_used,
                "remaining": remaining,
                "percent": round(platform_used / limit * 100, 1) if limit else 0,
            },
        },
        "series": buckets,
        "groups": groups,
        "logs": safe_logs,
    }
