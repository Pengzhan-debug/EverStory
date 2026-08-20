"""CLI: python -m everstory.eval [--mode stub|api] [--out docs/eval-report.md]"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config import LLM_MODE, build_role_client, load_providers
from ..llm.client import LLMClient
from .runner import run_eval, to_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EverStory benchmark.")
    parser.add_argument("--mode", choices=["stub", "api"], default=LLM_MODE)
    parser.add_argument(
        "--providers",
        default="",
        help="Comma-separated provider names (from .env); empty = all configured",
    )
    parser.add_argument(
        "--role-mix",
        action="store_true",
        help="Run once with strong/cheap roles routed per LLM_ROLE_STRONG / LLM_ROLE_CHEAP",
    )
    parser.add_argument("--out", default="docs/eval-report.md")
    args = parser.parse_args()

    if args.mode == "stub":
        client = LLMClient(mode="stub")
        results = run_eval(client, provider="stub")
    elif args.role_mix:
        client = build_role_client(mode="api")
        if not client.strong_api_key or not client.cheap_api_key:
            print("role-mix requires API keys for both roles (see LLM_ROLE_STRONG/LLM_ROLE_CHEAP).")
            return 1
        print(
            f"evaluating role-mix: strong={client.strong_model} @ {client.strong_base_url}, "
            f"cheap={client.cheap_model} @ {client.cheap_base_url}"
        )
        results = run_eval(client, provider="role-mix")
    else:
        providers = load_providers()
        requested = [p.strip() for p in args.providers.split(",") if p.strip()]
        if requested:
            providers = [p for p in providers if p.name in requested]
        results = []
        for provider in providers:
            if not provider.api_key:
                print(
                    f"skip provider '{provider.name}': no API key "
                    f"(LLM_PROVIDER_{provider.name.upper()}_API_KEY / LLM_API_KEY)"
                )
                continue
            client = LLMClient(
                mode="api",
                base_url=provider.base_url,
                api_key=provider.api_key,
                strong_model=provider.strong_model,
                cheap_model=provider.cheap_model,
            )
            print(f"evaluating provider '{provider.name}' ...")
            results.extend(run_eval(client, provider=provider.name))
        if not results:
            print("No providers configured with API keys; aborting.")
            return 1

    markdown = to_markdown(results, mode=client.mode)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
