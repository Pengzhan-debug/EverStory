"""Trajectory recording and abstracted fact extraction for rule induction."""

from __future__ import annotations

from typing import Any


def extract_facts(state, action) -> tuple[set[str], int]:
    """Render the world state as a set of abstracted predicates.

    Entity ids that appear in the action's params are replaced by role tokens
    (``$item``, ``$target``, ``$to``, ``$recipient``), the actor becomes
    ``$actor``, and the actor's current location becomes ``$here``. This lets
    rules learned from concrete trajectories generalize across entities.
    """
    actor_id = action.actor_id
    here = state.entities[actor_id].location_id
    roles = {"$actor": actor_id}
    for key, value in (action.params or {}).items():
        roles[f"${key}"] = value

    def abst(entity_id: str) -> str:
        for token, eid in roles.items():
            if eid == entity_id:
                return token
        return entity_id

    facts: set[str] = set()
    for e in state.entities.values():
        eid = abst(e.id)
        loc = e.location_id
        if loc:
            if e.id == actor_id:
                # Actor location stays concrete so location changes are
                # detectable as effects (e.g. +at($actor,$to)).
                l = abst(loc)
            elif loc == "inventory":
                l = "inventory"
            elif loc == here:
                l = "$here"
            else:
                l = abst(loc)
            facts.add(f"at({eid},{l})")

        if e.kind.value == "item":
            if e.owner_id:
                facts.add(f"owner({eid},{abst(e.owner_id)})")
            else:
                facts.add(f"unowned({eid})")
        for attr in ("locked", "filled", "lit"):
            if attr in e.attributes:
                facts.add(f"{attr}({eid})" if e.attributes[attr] else f"not_{attr}({eid})")
        if "unlock_key" in e.attributes:
            facts.add(f"key_for({eid},{abst(e.attributes['unlock_key'])})")
        if "contains" in e.attributes:
            for c in e.attributes["contains"]:
                facts.add(f"contains({eid},{abst(c)})")
        if e.kind.value == "location":
            for c in e.attributes.get("connections", []):
                a_end = "$here" if e.id == here else abst(e.id)
                b_end = "$here" if c == here else abst(c)
                facts.add(f"connected({a_end},{b_end})")

    for name, value in state.flags.items():
        facts.add(f"flag({name})" if value else f"not_flag({name})")

    return facts, state.time
