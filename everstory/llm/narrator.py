"""Grounded narrator: prose generated from *actual* engine results."""

from __future__ import annotations

from ..config import LLM_MODEL_CHEAP

NARRATE_SYSTEM = """You are the narrator of a deterministic text-adventure world.
You receive: the world summary, the player's input, and the engine's results.
Describe what happens in 2-4 vivid sentences. STRICT RULES:
- Only describe things that are true according to the engine results.
- If an action was rejected, describe the refusal plainly (e.g. "The chest is locked.").
- Never invent items, characters, locations, or events.
- Never mention an engine, rules, or systems.
"""


def narrate(
    client,
    context_text: str,
    model: str | None = None,
) -> str:
    model = model or LLM_MODEL_CHEAP
    messages = [
        {"role": "system", "content": NARRATE_SYSTEM},
        {"role": "user", "content": context_text},
    ]
    return client.chat(messages, model=model).strip()


def narrate_stub(session, results, user_text: str) -> str:
    """Deterministic template narration used in stub mode and tests."""
    parts: list[str] = []
    for res in results:
        a = res.action
        if a.action_type == "move" and res.ok:
            parts.append(f"You make your way to the {session.state.entity(a.params['to']).name}.")
        elif a.action_type == "take" and res.ok:
            parts.append(f"You pick up the {session.state.entity(a.params['item']).name}.")
        elif a.action_type == "give" and res.ok:
            parts.append(f"You hand over the {session.state.entity(a.params['item']).name}.")
        elif a.action_type == "wait" and res.ok:
            parts.append("Time passes.")
        else:
            parts.append(res.message)
    if not parts:
        parts.append("Nothing happens.")
    return " ".join(parts)
