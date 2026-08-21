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


def long_wander(turns: int) -> Episode:
    """A long, low-variance wandering episode for memory-decay measurement.

    The world facts stay constant (the key stays in the cave, the chest stays
    locked, the oil can stays in the boat shed), so any recall loss over the
    horizon is purely a memory/architecture effect.
    """
    loop = [
        "move to lighthouse_ground",
        "talk to mara",
        "move to cliff_path",
        "move to cave",
        "wait",
        "move to cliff_path",
        "move to lighthouse_ground",
        "talk to mara",
        "move to cottage",
        "move to dock",
        "move to boat_shed",
        "wait",
        "move to dock",
        "move to cottage",
        "wait",
    ]
    steps = [loop[i % len(loop)] for i in range(turns)]
    return Episode(
        name=f"long_wander_{turns}",
        steps=steps,
        facts=[
            Fact("Where is the rusty key?", "sea cave"),
            Fact("Where is the oil can?", "boat shed"),
            Fact("Is the iron chest locked?", "yes"),
        ],
    )
