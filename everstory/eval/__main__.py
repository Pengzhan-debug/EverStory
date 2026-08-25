"""CLI: python -m everstory.eval [--mode stub|api] [--out docs/eval-report.md]"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config import build_client
from ..llm.client import LLMClient
from .runner import run_eval, run_long_eval, to_long_markdown, to_markdown
from .team import run_team_eval, to_team_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EverStory benchmark.")
    parser.add_argument("--mode", choices=["stub", "api"], default="")
    parser.add_argument(
        "--long",
        action="store_true",
        help="Also run the long-horizon memory-decay benchmark",
    )
    parser.add_argument("--horizon", type=int, default=60)
    parser.add_argument(
        "--contradictions",
        action="store_true",
        help="Measure narration contradiction rate (LLM-judge; api mode only)",
    )
    parser.add_argument("--out", default="docs/eval-report.md")
    parser.add_argument(
        "--team",
        action="store_true",
        help="Run the multi-agent investigation and cost benchmark",
    )
    parser.add_argument(
        "--team-only",
        action="store_true",
        help="Run only the multi-agent benchmark (useful for CI and cost checks)",
    )
    args = parser.parse_args()

    if args.mode == "stub":
        client = LLMClient(mode="stub")
        label = "stub"
    else:
        client = build_client(mode="api")
        if not client.strong_api_key or not client.cheap_api_key:
            print(
                "API keys are missing. Fill LLM_STRONG_API_KEY / LLM_CHEAP_API_KEY "
                "in .env, or run with --mode stub."
            )
            return 1
        label = f"{client.strong_model}+{client.cheap_model}"
        print(f"evaluating with strong={client.strong_model} @ {client.strong_base_url}")
        print(f"             cheap  ={client.cheap_model} @ {client.cheap_base_url}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.team_only:
        markdown = "# EverStory Multi-Agent Evaluation Report\n\n" + to_team_markdown(
            run_team_eval(client, provider=label)
        )
        out.write_text(markdown, encoding="utf-8")
        print(markdown)
        print(f"\nReport written to {out}")
        return 0

    results = run_eval(client, provider=label)
    markdown = to_markdown(results, mode=client.mode)
    out.write_text(markdown, encoding="utf-8")  # persist before the long run
    if args.long:
        print(f"running long-horizon benchmark ({args.horizon} turns) ...")
        long_results = run_long_eval(
            client,
            horizon=args.horizon,
            provider=label,
            contradiction_every=5 if args.contradictions else 0,
        )
        markdown += "\n" + to_long_markdown(long_results)
    if args.team:
        print("running multi-agent investigation benchmark ...")
        markdown += "\n" + to_team_markdown(run_team_eval(client, provider=label))
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
