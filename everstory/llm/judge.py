"""Consistency judge: does the narration contradict the ground-truth facts?"""

from __future__ import annotations

import json

from ..config import LLM_STRONG_MODEL

JUDGE_SYSTEM = """You check whether a narrator's prose contradicts the ground-truth
facts of a world. Facts are listed as 'FACT: ...'. The prose is 'NARRATION: ...'.
Respond with JSON only: {"consistent": true|false, "issues": ["..."]}.
Only report an issue if the prose directly contradicts a fact or invents
entities/items/events not present in the facts."""


def check_consistency(
    client,
    narration: str,
    facts: list[str],
    model: str | None = None,
) -> tuple[bool, list[str]]:
    if client.mode == "stub":
        return True, []
    model = model or LLM_STRONG_MODEL
    payload = (
        "FACTS:\n"
        + "\n".join(f"FACT: {f}" for f in facts)
        + f"\n\nNARRATION:\n{narration}"
    )
    content = client.chat(
        [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": payload},
        ],
        model=model,
        json_mode=True,
    )
    try:
        data = json.loads(content)
        return bool(data.get("consistent", True)), list(data.get("issues", []))
    except json.JSONDecodeError:
        return True, []
