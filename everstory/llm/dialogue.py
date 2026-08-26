"""In-character NPC dialogue.

The engine still owns the world; dialogue is *presentation*. The LLM speaks as
the character, constrained by the character's persona and by the scripted
dialogue lines that encode what the character actually knows at this point of
the story. The character never changes state — it can only talk.
"""

from __future__ import annotations

from ..config import LLM_CHEAP_MODEL
from .language import ensure_output_locale, guarded_stream

SYSTEM_PROMPT = """You are an NPC in a text-adventure game, speaking in character.
STRICT RULES:
- Reply as the named character, in their voice and personality, as *spoken
  dialogue* (1-3 sentences). Do not narrate actions or describe yourself in
  third person.
- You may elaborate on the canonical line you know, but never contradict it.
- Only know what this character would know from the world state and their
  story facts. If asked about something they would not know, deflect naturally
  or steer the conversation back.
- Never claim that actions happened, items changed hands, or the world changed.
- Do not mention engines, rules, or systems.
"""


def _language_rule(locale: str) -> str:
    return (
        "\nMANDATORY OUTPUT LANGUAGE: Simplified Chinese (简体中文)."
        if locale == "zh-CN"
        else "\nMANDATORY OUTPUT LANGUAGE: English."
    )


def _persona(character) -> str:
    return (
        character.attributes.get("persona")
        or character.description
        or "A quiet inhabitant of this world."
    )


def _recent_dialogue(history: list[dict], limit: int = 6) -> str:
    if not history:
        return "(none yet)"
    lines = []
    for entry in history[-limit:]:
        who = entry.get("speaker", "?")
        what = entry.get("text", "")
        lines.append(f"{who}: {what}")
    return "\n".join(lines)


def _reply_instruction(locale: str) -> str:
    return (
        "\n只用简体中文回答；即使人物名和背景资料是英文，也不要用英文句子。"
        if locale == "zh-CN"
        else "\nReply in English only, even if the background contains another language."
    )


def npc_reply(
    client,
    character,
    world_context: str,
    player_text: str,
    dialogue_history: list[dict] | None = None,
    canonical_line: str = "",
    model: str | None = None,
    locale: str = "en",
) -> str:
    """A natural, in-character spoken reply grounded in the world state."""
    model = model or LLM_CHEAP_MODEL
    history = dialogue_history or []
    payload = (
        f"Character: {character.name}\n"
        f"Appearance/knowledge: {character.description}\n"
        f"Personality: {_persona(character)}\n"
        f"Canonical line you just delivered (elaborate, never contradict): "
        f"{canonical_line or '(none)'}\n\n"
        f"World now:\n{world_context}\n\n"
        f"Recent conversation:\n{_recent_dialogue(history)}\n\n"
        f"Player says: {player_text}\n\n"
        f"Reply as {character.name}:{_reply_instruction(locale)}"
    )
    content = client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT + _language_rule(locale)},
            {"role": "user", "content": payload},
        ],
        model=model,
        role="cheap",
        agent="npc_dialogue",
    ).strip()
    return ensure_output_locale(
        client,
        content or canonical_line,
        locale,
        agent="npc_dialogue",
        fallback=(
            f"{character.name} 沉默片刻，提醒你继续核对已经确认的线索。"
            if locale == "zh-CN"
            else f"{character.name} falls quiet and urges you to verify the confirmed clues."
        ),
    )


def npc_reply_stream(
    client,
    character,
    world_context: str,
    player_text: str,
    dialogue_history: list[dict] | None = None,
    canonical_line: str = "",
    model: str | None = None,
    locale: str = "en",
):
    """Streamed version of npc_reply()."""
    model = model or LLM_CHEAP_MODEL
    history = dialogue_history or []
    payload = (
        f"Character: {character.name}\n"
        f"Appearance/knowledge: {character.description}\n"
        f"Personality: {_persona(character)}\n"
        f"Canonical line you just delivered (elaborate, never contradict): "
        f"{canonical_line or '(none)'}\n\n"
        f"World now:\n{world_context}\n\n"
        f"Recent conversation:\n{_recent_dialogue(history)}\n\n"
        f"Player says: {player_text}\n\n"
        f"Reply as {character.name}:{_reply_instruction(locale)}"
    )
    chunks = client.chat_stream(
        [
            {"role": "system", "content": SYSTEM_PROMPT + _language_rule(locale)},
            {"role": "user", "content": payload},
        ],
        model=model,
        role="cheap",
        agent="npc_dialogue",
    )
    yield from guarded_stream(
        client,
        chunks,
        locale,
        agent="npc_dialogue",
        fallback=(
            f"{character.name} 沉默片刻，提醒你继续核对已经确认的线索。"
            if locale == "zh-CN"
            else f"{character.name} falls quiet and urges you to verify the confirmed clues."
        ),
    )


def npc_reply_stub(
    character, player_text: str = "", canonical_line: str = "", locale: str = "en"
) -> str:
    """Deterministic stub: returns the scripted line as spoken dialogue."""
    line = canonical_line or character.attributes.get("dialogue", {}).get(
        "default", f"{character.name} has nothing to say."
    )
    if locale == "zh-CN":
        translated = {
            'The keeper eyes you wearily. "The light has been out for a year, and the sea has grown restless."': "守塔人疲惫地打量着你。‘灯已经熄灭一年了，海也变得越来越不安。’",
            '"Some say the old keeper still walks the cliffs at night. Finish what he started — light the lamp."': "‘有人说老守塔人夜里仍在悬崖上游荡。完成他未竟的事——点亮灯塔。’",
        }.get(line)
        return translated or f"{character.name} 沉默片刻，提醒你继续核对已经确认的线索。"
    return f"{character.name}: {line}"
