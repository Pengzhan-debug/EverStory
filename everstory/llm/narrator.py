"""Grounded narrator: prose generated from *actual* engine results."""

from __future__ import annotations

from ..config import LLM_CHEAP_MODEL

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
    model = model or LLM_CHEAP_MODEL
    messages = [
        {"role": "system", "content": NARRATE_SYSTEM},
        {"role": "user", "content": context_text},
    ]
    return client.chat(
        messages, model=model, role="cheap", agent="narrator"
    ).strip()


def narrate_stream(
    client,
    context_text: str,
    model: str | None = None,
):
    """Streamed version of narrate()."""
    model = model or LLM_CHEAP_MODEL
    messages = [
        {"role": "system", "content": NARRATE_SYSTEM},
        {"role": "user", "content": context_text},
    ]
    yield from client.chat_stream(
        messages, model=model, role="cheap", agent="narrator"
    )


CHAT_SYSTEM = """You are the voice of a living world in a text-adventure game.
The player is speaking to you directly — not necessarily requesting an action.
Answer naturally and briefly (1-3 sentences), in a vivid, literary style.
STRICT RULES:
- Ground everything in the provided world state.
- Never invent items, characters, locations, events, or state changes.
- If the player's question cannot be answered from the world state, answer with
  atmosphere or gently steer them toward an action they could take.
- Never mention engines, rules, or systems.
"""


def chat_reply(
    client,
    context_text: str,
    user_text: str,
    model: str | None = None,
) -> str:
    """Conversational reply when the player is chatting, not acting."""
    model = model or LLM_CHEAP_MODEL
    messages = [
        {"role": "system", "content": CHAT_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{context_text}\n\nPlayer says: {user_text}\n\nReply:"
            ),
        },
    ]
    return client.chat(
        messages, model=model, role="cheap", agent="narrator"
    ).strip()


def chat_reply_stream(
    client,
    context_text: str,
    user_text: str,
    model: str | None = None,
):
    """Streamed version of chat_reply()."""
    model = model or LLM_CHEAP_MODEL
    messages = [
        {"role": "system", "content": CHAT_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{context_text}\n\nPlayer says: {user_text}\n\nReply:"
            ),
        },
    ]
    yield from client.chat_stream(
        messages, model=model, role="cheap", agent="narrator"
    )


def chat_reply_stub(user_text: str) -> str:
    """Deterministic stub for tests and offline mode."""
    return (
        "The wind stirs around you. If you want to do something, say it plainly "
        f"(you said: {user_text[:60]})"
    )


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
