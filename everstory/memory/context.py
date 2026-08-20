"""Context builder: renders the structured world state for the LLM."""

from __future__ import annotations

from ..config import LLM_MODEL_STRONG
from ..models import EntityKind


def entity_cards(session, actor_id: str, limit: int = 12) -> list[str]:
    st = session.state
    actor = st.entity(actor_id)
    cards: list[str] = []

    for e in st.entities.values():
        if e.id == actor_id:
            continue
        if e.kind == EntityKind.CHARACTER and e.location_id == actor.location_id:
            cards.append(f"{e.name}: {e.description}")

    inv = [
        e
        for e in st.entities.values()
        if e.owner_id == actor_id and e.location_id == "inventory"
    ]
    if inv:
        cards.append("Your inventory: " + ", ".join(e.name for e in inv))

    visible = [
        e
        for e in st.entities.values()
        if e.kind == EntityKind.ITEM
        and e.location_id == actor.location_id
        and e.owner_id is None
    ]
    if visible:
        cards.append("Here you can see: " + ", ".join(e.name for e in visible))

    quests = [e for e in st.entities.values() if e.kind == EntityKind.QUEST]
    if quests:
        lines = []
        for q in quests:
            done = bool(st.flags.get(q.attributes.get("flag", "")))
            lines.append(("done" if done else "pending") + ": " + q.name)
        cards.append("Quests: " + "; ".join(lines))

    return cards[:limit]


def build_context(
    session, actor_id: str, recent_events: list[str], summary: str = ""
) -> str:
    st = session.state
    actor = st.entity(actor_id)
    loc = st.entity(actor.location_id)
    lines = [
        f"Time: {st.time} | Turn: {st.turn}",
        f"Location: {loc.name}. {loc.description}",
    ]
    lines += entity_cards(session, actor_id)
    if summary:
        lines.append("Story so far (summary): " + summary)
    if recent_events:
        lines.append("Recent events:")
        lines += [f"- {e}" for e in recent_events[-6:]]
    return "\n".join(lines)


def summarize(
    client,
    event_text: str,
    previous: str = "",
    model: str | None = None,
) -> str:
    """Rolling summary. Stub mode concatenates deterministically; API mode
    asks the model to compress the events."""
    if client.mode == "stub":
        merged = (previous + " " + event_text).strip()
        return merged[:300]
    model = model or LLM_MODEL_STRONG
    prompt = (
        "Compress the following game events into a short summary (max 120 words). "
        "Keep concrete facts: locations, items, ownership, locks, and quest progress.\n\n"
        f"Previous summary:\n{previous or '(none)'}\n\n"
        f"New events:\n{event_text}\n\nSummary:"
    )
    return client.chat(
        [
            {"role": "system", "content": "You write concise factual game summaries."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    ).strip()
