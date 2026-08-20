"""Interactive CLI for EverStory (structured commands in v0.1)."""

from __future__ import annotations

import re
import sys

from .commands import parse_structured
from .engine import WorldSession
from .models import Action
from .worlds import load_world

WORLD_NAME = "lost_lighthouse"

CMD_ROLLBACK = re.compile(r"^rollback\s+(\d+)$", re.I)

HELP_TEXT = """\
Commands:
  look | l                 describe the current place
  inventory | i            list what you carry
  where                    show your location, turn and time
  quests | q               show quest status
  move to <place>          go somewhere connected
  take <item>              pick up an item
  give <item> to <person>  hand an item over
  use <item> on <target>   use an item (e.g. key on chest)
  open <container>         open a chest or door
  talk to <person>         talk to a character
  wait                     let time pass
  rollback <turn>          rewind the world to an earlier turn
  quit                     leave the game
"""


def run_action(session: WorldSession, action_type: str, params: dict) -> str:
    res = session.act(
        Action(action_type=action_type, actor_id=session.player_id(), params=params)
    )
    if not res.ok:
        return res.message
    if action_type == "talk":
        name = session.state.entity(res.action.params["target"]).name
        return f"You talk with {name}. (dialogue arrives in v0.2 with the LLM layer)"
    return res.message


def handle_command(session: WorldSession, line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    low = line.lower()
    actor = session.player_id()

    if low in ("look", "l"):
        return session.visible_summary(actor)
    if low in ("inventory", "i"):
        return session.inventory_summary(actor)
    if low == "where":
        st = session.state
        loc = st.entity(st.entity(actor).location_id)
        return f"You are at the {loc.name}. (turn {st.turn}, time {st.time})"
    if low in ("quests", "quest", "q"):
        return session.quest_summary()
    if low == "wait":
        session.act(Action(action_type="wait", actor_id=actor))
        return f"Time passes. (time now {session.state.time})"
    if low in ("help", "h"):
        return HELP_TEXT
    if low in ("quit", "exit"):
        raise SystemExit

    actions = parse_structured(line)
    if actions:
        outputs = []
        for proposal in actions:
            outputs.append(
                run_action(
                    session,
                    proposal["type"],
                    proposal.get("params") or {},
                )
            )
        return "\n".join(outputs)
    m = CMD_ROLLBACK.match(line)
    if m:
        turn = int(m.group(1))
        session.rollback(turn)
        return f"Rolled back to turn {turn}."
    return "I don't understand that. Try 'help'."


def main() -> None:
    world_name = sys.argv[1] if len(sys.argv) > 1 else WORLD_NAME
    session = WorldSession(load_world(world_name))
    print(f"=== {session.title} ===")
    print("Type 'help' for commands.\n")
    print(session.visible_summary(session.player_id()))
    print()
    for line in sys.stdin:
        try:
            out = handle_command(session, line)
        except SystemExit:
            print("Goodbye.")
            return
        except KeyError:
            out = "I don't know what that refers to."
        if out:
            print(out)
        print()


if __name__ == "__main__":
    main()
