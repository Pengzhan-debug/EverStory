"""CLI: python -m everstory.eval [--mode stub|api] [--out docs/eval-report.md]"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_MODE
from ..llm.client import LLMClient
from .runner import run_eval, to_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EverStory benchmark.")
    parser.add_argument("--mode", choices=["stub", "api"], default=LLM_MODE)
    parser.add_argument("--out", default="docs/eval-report.md")
    args = parser.parse_args()

    client = LLMClient(mode=args.mode, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    if client.mode == "api" and not client.api_key:
        print("LLM_API_KEY is not set. Run with --mode stub or set the env var.")
        return 1

    results = run_eval(client)
    markdown = to_markdown(results, mode=client.mode)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
