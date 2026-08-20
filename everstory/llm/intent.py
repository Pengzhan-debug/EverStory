"""Intent parser: free-text player input -> structured action proposals."""

from __future__ import annotations

import json

from ..commands import parse_structured
from ..config import LLM_STRONG_MODEL

SYSTEM_PROMPT = """You are the intent parser of a deterministic world engine.
Given the player's text and the current world state, emit the player's actions as JSON.
Respond with JSON only, in this exact shape:
{"actions": [{"type": "<action_type>", "params": {...}}]}

Allowed action types and params:
- move: {"to": "<location name>"}
- take: {"item": "<item name>"}
- give: {"item": "<item name>", "recipient": "<character name>"}
- use: {"item": "<item name>", "target": "<target name>"}
- open: {"target": "<container or door name>"}
- talk: {"target": "<character name>"}
- wait: {} (no params)

Rules:
- Use entity names exactly as written in the world description.
- If the player's text contains several actions, emit them in order.
- If an action is impossible or unclear, still emit your best interpretation;
  the engine will validate it and reject it if it is not possible.
"""


def parse_actions(
    text: str, world_summary: str, client, model: str | None = None
) -> list[dict]:
    model = model or LLM_STRONG_MODEL
    if client.mode == "stub":
        return parse_structured(text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"World now:\n{world_summary}\n\n"
                f"Player says: {text}\n\nActions:"
            ),
        },
    ]
    content = client.chat(messages, model=model, json_mode=True)
    try:
        data = json.loads(content)
        actions = data.get("actions") or []
        return [a for a in actions if isinstance(a, dict) and a.get("type")]
    except json.JSONDecodeError:
        return []
