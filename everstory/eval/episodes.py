"""Scripted evaluation episodes with ground-truth fact questions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Fact:
    question: str
    answer: str  # scoring substring (case-insensitive)


@dataclass
class Episode:
    name: str
    steps: list[str]
    facts: list[Fact] = field(default_factory=list)


EPISODES: list[Episode] = [
    Episode(
        name="lost_key",
        steps=[
            "move to lighthouse_ground",
            "move to cliff_path",
            "move to cave",
            "take rusty key",
            "move to cliff_path",
            "move to lighthouse_ground",
            "use rusty key on chest",
            "open chest",
            "take flint",
        ],
        facts=[
            Fact("Where is the rusty key?", "inventory"),
            Fact("Who is carrying the flint?", "you"),
            Fact("Is the iron chest locked?", "no"),
        ],
    ),
    Episode(
        name="gift_for_mara",
        steps=[
            "move to dock",
            "move to boat_shed",
            "take oil can",
            "move to dock",
            "move to cottage",
            "move to lighthouse_ground",
            "give oil can to mara",
        ],
        facts=[Fact("Who has the oil can?", "mara")],
    ),
    Episode(
        name="light_the_lighthouse",
        steps=[
            "move to lighthouse_ground",
            "move to cliff_path",
            "move to cave",
            "take rusty key",
            "move to cliff_path",
            "move to lighthouse_ground",
            "use rusty key on chest",
            "open chest",
            "take flint",
            "move to cottage",
            "move to dock",
            "move to boat_shed",
            "take oil can",
            "move to dock",
            "move to cottage",
            "use oil can on lantern",
            "use flint on lantern",
        ],
        facts=[
            Fact("Is the lighthouse lit?", "yes"),
            Fact("Who is carrying the flint?", "you"),
        ],
    ),
]
