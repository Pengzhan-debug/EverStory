"""Run credential-safe health checks against configured model connections."""

from __future__ import annotations

import argparse
import concurrent.futures
import time

from everstory.config import build_client


def check(connection_id: str) -> dict:
    client = build_client(mode="api")
    connection = client.connections[connection_id]
    started = time.perf_counter()
    try:
        text = client.chat(
            [
                {
                    "role": "system",
                    "content": "Software integration health check. Reply with OK only.",
                },
                {"role": "user", "content": "Return OK."},
            ],
            temperature=0,
            connection_id=connection_id,
            agent="unassigned",
        )
        return {
            "id": connection_id,
            "name": connection["name"],
            "ok": text.strip().upper().startswith("OK"),
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "tokens": sum(client.last_usage.values()),
            "reply": text.strip().replace("\n", " ")[:40],
        }
    except Exception as exc:  # diagnostic CLI: preserve a bounded reason
        return {
            "id": connection_id,
            "name": connection["name"],
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "tokens": 0,
            "reply": str(exc).replace("\n", " ")[:180],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="volcengine_ark")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    client = build_client(mode="api")
    targets = [
        connection_id
        for connection_id, connection in client.connections.items()
        if connection.get("provider") == args.provider
    ]
    if not targets:
        print(f"No configured connections for provider: {args.provider}")
        return 2
    if any(not client.connections[target].get("api_key") for target in targets):
        print("Provider credential is not configured; no request was sent.")
        return 2

    print(f"Testing {len(targets)} {args.provider} connections (credentials hidden)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(check, targets))
    for result in results:
        state = "PASS" if result["ok"] else "FAIL"
        print(
            f"{state:4}  {result['name']:<34} "
            f"{result['latency_ms']:>6} ms  {result['tokens']:>5} tokens  {result['reply']}"
        )
    passed = sum(1 for result in results if result["ok"])
    print(f"Summary: {passed}/{len(results)} connections passed.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
