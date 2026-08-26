"""Output-language guardrails shared by story and agent responses."""

from __future__ import annotations

import re


_CJK = re.compile(r"[\u3400-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")


def matches_locale(text: str, locale: str) -> bool:
    """Return whether a response is materially written in the requested locale."""
    value = str(text or "").strip()
    if not value:
        return False
    cjk = len(_CJK.findall(value))
    latin = len(_LATIN.findall(value))
    if locale == "zh-CN":
        return cjk >= 2 and cjk * 5 >= latin
    return latin >= 2 and cjk * 6 < latin


def ensure_output_locale(
    client,
    text: str,
    locale: str,
    *,
    agent: str,
    fallback: str = "",
) -> str:
    """Translate a model response only when it ignored the requested language."""
    value = str(text or "").strip()
    if matches_locale(value, locale):
        return value
    target = "Simplified Chinese" if locale == "zh-CN" else "English"
    default = fallback or (
        "世界已经根据你的行动发生变化，请以调查日志中的已确认记录为准。"
        if locale == "zh-CN"
        else "The world has changed; use the confirmed investigation log as the record."
    )
    if not value:
        return default
    try:
        translated = client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        f"Translate the supplied game text into {target}. Preserve every fact, "
                        "name, uncertainty, and speaking voice. Add nothing. Return only the translation."
                    ),
                },
                {"role": "user", "content": value},
            ],
            temperature=0.1,
            role="cheap",
            agent=agent,
        ).strip()
        if matches_locale(translated, locale):
            return translated
    except Exception:
        pass
    return default


def guarded_stream(client, chunks, locale: str, *, agent: str, fallback: str = ""):
    """Preserve streaming for compliant text; buffer and repair wrong-language text."""
    buffered = ""
    streaming = False
    for chunk in chunks:
        if not chunk:
            continue
        buffered += chunk
        if streaming:
            yield chunk
        elif len(buffered.strip()) >= 12 and matches_locale(buffered, locale):
            streaming = True
            yield buffered
    if not streaming:
        yield ensure_output_locale(
            client, buffered, locale, agent=agent, fallback=fallback
        )
