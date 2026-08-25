"""Structured command parsing shared by the CLI and the stub intent parser."""

from __future__ import annotations

import re

MOVE = re.compile(r"^(?:go|move)(?:\s+to)?\s+(.+)$", re.I)
TAKE = re.compile(r"^take\s+(.+)$", re.I)
GIVE = re.compile(r"^give\s+(.+?)\s+to\s+(.+)$", re.I)
USE = re.compile(r"^use\s+(.+?)\s+(?:on|with)\s+(.+)$", re.I)
OPEN = re.compile(r"^open\s+(.+)$", re.I)
TALK = re.compile(r"^talk\s+(?:to\s+)?(.+)$", re.I)
EXAMINE = re.compile(r"^(?:examine|inspect|check)\s+(.+)$", re.I)
ACCUSE = re.compile(r"^accuse\s+(.+)$", re.I)


def parse_structured(text: str) -> list[dict]:
    """Parse simple structured commands into action proposals (deterministic)."""
    text = (text or "").strip()
    low = text.lower()
    m = MOVE.match(text)
    if m:
        return [{"type": "move", "params": {"to": m.group(1).strip()}}]
    m = TAKE.match(text)
    if m:
        return [{"type": "take", "params": {"item": m.group(1).strip()}}]
    m = GIVE.match(text)
    if m:
        return [
            {
                "type": "give",
                "params": {"item": m.group(1).strip(), "recipient": m.group(2).strip()},
            }
        ]
    m = USE.match(text)
    if m:
        return [
            {
                "type": "use",
                "params": {"item": m.group(1).strip(), "target": m.group(2).strip()},
            }
        ]
    m = OPEN.match(text)
    if m:
        return [{"type": "open", "params": {"target": m.group(1).strip()}}]
    m = TALK.match(text)
    if m:
        return [{"type": "talk", "params": {"target": m.group(1).strip()}}]
    m = EXAMINE.match(text)
    if m:
        return [{"type": "examine", "params": {"target": m.group(1).strip()}}]
    m = ACCUSE.match(text)
    if m:
        return [{"type": "accuse", "params": {"target": m.group(1).strip()}}]
    if low in ("wait", "wait a moment"):
        return [{"type": "wait", "params": {}}]
    return []
