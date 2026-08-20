"""World loaders. Worlds are declarative data (TOML)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ..models import Entity, EntityKind, Relationship, WorldState

WORLDS_DIR = Path(__file__).parent


class WorldDef:
    def __init__(self, title: str, initial_state: WorldState) -> None:
        self.title = title
        self.initial_state = initial_state


def load_world(name: str) -> WorldDef:
    path = WORLDS_DIR / f"{name}.toml"
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    state = WorldState()
    player_id: str | None = None

    for row in data.get("entities", []):
        eid: str = row["id"]
        kind = EntityKind(row["kind"])
        ent = Entity(
            id=eid,
            kind=kind,
            name=row["name"],
            description=row.get("description", ""),
            attributes=dict(row.get("attributes", {})),
            location_id=row.get("location"),
            owner_id=row.get("owner"),
        )
        state.entities[eid] = ent
        if kind == EntityKind.CHARACTER and row.get("is_player"):
            player_id = eid

    for row in data.get("relationships", []):
        state.relationships.append(
            Relationship(
                type=row["type"],
                source_id=row["from"],
                target_id=row["to"],
                properties=dict(row.get("properties", {})),
            )
        )

    state.flags = dict(data.get("flags", {}))
    state.time = int(data.get("time", 0))
    state.turn = int(data.get("turn", 0))

    if player_id is None:
        raise ValueError("World must declare exactly one player entity (is_player = true)")
    return WorldDef(title=data.get("title", name), initial_state=state)
