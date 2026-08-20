"""Core domain models for EverStory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

INVENTORY_ID = "inventory"


class EntityKind(str, Enum):
    CHARACTER = "character"
    ITEM = "item"
    LOCATION = "location"
    QUEST = "quest"
    CONCEPT = "concept"


@dataclass
class Entity:
    id: str
    kind: EntityKind
    name: str
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    location_id: str | None = None
    owner_id: str | None = None

    @property
    def in_inventory(self) -> bool:
        return self.location_id == INVENTORY_ID and self.owner_id is not None


@dataclass
class Relationship:
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    action_type: str
    actor_id: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class ActionResult:
    ok: bool
    action: Action
    message: str
    effects: list[str] = field(default_factory=list)


@dataclass
class EventRecord:
    turn: int
    actor_id: str
    action: Action
    ok: bool
    message: str
    state_hash: str


@dataclass
class WorldState:
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    time: int = 0
    turn: int = 0
    flags: dict[str, Any] = field(default_factory=dict)

    def entity(self, entity_id: str) -> Entity:
        return self.entities[entity_id]

    def relationships_from(
        self, source_id: str, rel_type: str | None = None
    ) -> list[Relationship]:
        return [
            r
            for r in self.relationships
            if r.source_id == source_id and (rel_type is None or r.type == rel_type)
        ]

    def has_relationship(self, rel_type: str, source_id: str, target_id: str) -> bool:
        return any(
            r.type == rel_type and r.source_id == source_id and r.target_id == target_id
            for r in self.relationships
        )

    def snapshot_hash(self) -> str:
        """Canonical hash of the world state, used for snapshots and eval."""
        # NOTE: `turn` is intentionally excluded: it is timeline metadata, not
        # world content. Rejected actions advance the turn but leave the world
        # unchanged, and that must be visible in the hash.
        payload = {
            "time": self.time,
            "flags": dict(sorted(self.flags.items(), key=lambda kv: kv[0])),
            "entities": sorted(
                (
                    e.id,
                    e.kind.value,
                    e.name,
                    dict(sorted(e.attributes.items(), key=lambda kv: kv[0])),
                    e.location_id,
                    e.owner_id,
                )
                for e in self.entities.values()
            ),
            "relationships": sorted(
                (r.type, r.source_id, r.target_id) for r in self.relationships
            ),
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
