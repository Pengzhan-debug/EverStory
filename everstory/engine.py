"""EverStory rule engine.

The engine owns the world. An LLM (or a user, or a script) *proposes* actions;
the engine validates them against declarative rules, applies deterministic
effects, records an event, and snapshots the state. The LLM never mutates
state directly.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .models import (
    INVENTORY_ID,
    Action,
    ActionResult,
    EntityKind,
    EventRecord,
    WorldState,
)
from .trajectory import extract_facts


@dataclass
class Check:
    """A declarative precondition. subject/target may be entity ids or
    references like ``$actor``, ``$here``, ``$param.<name>``."""

    kind: str
    subject: str = "$actor"
    target: str = ""
    attr: str = ""
    value: Any = None
    message: str = ""


@dataclass
class Effect:
    """A declarative state transition, applied only if all checks pass."""

    kind: str
    subject: str = "$actor"
    target: str = ""
    attr: str = ""
    value: Any = None


@dataclass
class ActionRule:
    action_type: str
    description: str
    checks: list[Check]
    effects: list[Effect]


class RuleEngine:
    """Holds the declarative action library."""

    def __init__(self, rules: dict[str, ActionRule] | None = None) -> None:
        self.rules: dict[str, ActionRule] = rules or {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.rules.update(
            {
                "move": ActionRule(
                    action_type="move",
                    description="Move to a connected location.",
                    checks=[
                        Check(
                            "connected",
                            subject="$here",
                            target="$param.to",
                            message="You can't go that way from here.",
                        ),
                    ],
                    effects=[
                        Effect("set_location", subject="$actor", target="$param.to"),
                        Effect("advance_time", value=1),
                    ],
                ),
                "take": ActionRule(
                    action_type="take",
                    description="Take an item that is here and unowned.",
                    checks=[
                        Check(
                            "here",
                            subject="$param.item",
                            target="$here",
                            message="That isn't here.",
                        ),
                        Check(
                            "not_owned",
                            subject="$param.item",
                            message="Someone already owns that.",
                        ),
                    ],
                    effects=[Effect("set_owner", subject="$param.item", target="$actor")],
                ),
                "give": ActionRule(
                    action_type="give",
                    description="Give an item you own to someone in the same place.",
                    checks=[
                        Check(
                            "inventory",
                            subject="$param.item",
                            target="$actor",
                            message="You don't have that.",
                        ),
                        Check(
                            "same_location",
                            subject="$param.recipient",
                            target="$actor",
                            message="They aren't here.",
                        ),
                    ],
                    effects=[
                        Effect("set_owner", subject="$param.item", target="$param.recipient")
                    ],
                ),
                "use": ActionRule(
                    action_type="use",
                    description="Use an item from your inventory.",
                    checks=[
                        Check(
                            "inventory",
                            subject="$param.item",
                            target="$actor",
                            message="You don't have that.",
                        ),
                    ],
                    effects=[],
                ),
                "open": ActionRule(
                    action_type="open",
                    description="Open a container or door.",
                    checks=[
                        Check(
                            "here",
                            subject="$param.target",
                            target="$here",
                            message="That isn't here.",
                        ),
                    ],
                    effects=[],
                ),
                "talk": ActionRule(
                    action_type="talk",
                    description="Talk to a character in the same place.",
                    checks=[
                        Check(
                            "same_location",
                            subject="$param.target",
                            target="$actor",
                            message="They aren't here.",
                        ),
                    ],
                    effects=[Effect("advance_time", value=1)],
                ),
                "examine": ActionRule(
                    action_type="examine",
                    description="Closely examine an item that is here or in your inventory.",
                    checks=[
                        Check(
                            "accessible",
                            subject="$param.target",
                            target="$actor",
                            message="That isn't available to examine.",
                        ),
                    ],
                    effects=[Effect("advance_time", value=1)],
                ),
                "accuse": ActionRule(
                    action_type="accuse",
                    description="Confront a present suspect with the confirmed case evidence.",
                    checks=[
                        Check(
                            "same_location",
                            subject="$param.target",
                            target="$actor",
                            message="The suspect must be present for a formal accusation.",
                        ),
                    ],
                    effects=[Effect("advance_time", value=1)],
                ),
                "wait": ActionRule(
                    action_type="wait",
                    description="Wait; time passes.",
                    checks=[],
                    effects=[Effect("advance_time", value=1)],
                ),
            }
        )


class WorldSession:
    """A running world: state, rules, event history, and snapshots."""

    def __init__(
        self,
        world,
        rules: dict[str, ActionRule] | None = None,
        collect_transitions: bool = False,
    ) -> None:
        self.title: str = world.title
        self.world_name: str = getattr(world, "name", "world")
        self.engine = RuleEngine(rules)
        self.state: WorldState = copy.deepcopy(world.initial_state)
        self.history: list[EventRecord] = []
        self.snapshots: dict[int, tuple[WorldState, str]] = {}
        self.collect_transitions = collect_transitions
        self.transitions: list[dict] = []
        self._current: Action | None = None
        self._snapshot()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def resolve_name(self, name: str) -> str | None:
        """Resolve an entity by id, exact name, unique prefix, or unique substring."""
        n = (name or "").strip().lower()
        if not n:
            return None
        if n in self.state.entities:
            return n
        exact = [e.id for e in self.state.entities.values() if e.name.lower() == n]
        if len(exact) == 1:
            return exact[0]
        prefix = [e.id for e in self.state.entities.values() if e.name.lower().startswith(n)]
        if len(prefix) == 1:
            return prefix[0]
        sub = [e.id for e in self.state.entities.values() if n in e.name.lower()]
        if len(sub) == 1:
            return sub[0]
        return None

    def resolve_ref(self, token: str, action: Action | None = None) -> str | None:
        action = action or self._current
        if not action:
            return None
        if token.startswith("$param."):
            return (action.params or {}).get(token[len("$param."):])
        if token == "$actor":
            return action.actor_id
        if token == "$here":
            ent = self.state.entities.get(action.actor_id)
            return ent.location_id if ent else None
        return token

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------
    def act(self, action: Action) -> ActionResult:
        # Resolve free-text params (entity names) to ids.
        resolved: dict[str, str] = {}
        for key, value in (action.params or {}).items():
            rid = self.resolve_name(value)
            resolved[key] = rid if rid is not None else value
        action = Action(action.action_type, action.actor_id, resolved)
        self._current = action
        if self.collect_transitions:
            before_facts, before_time = extract_facts(self.state, action)

        rule = self.engine.rules.get(action.action_type)
        if rule is None:
            res = ActionResult(
                ok=False, action=action, message=f"Unknown action: {action.action_type}"
            )
        else:
            failures: list[str] = []
            for chk in rule.checks:
                ok, msg = self._eval_check(chk, action)
                if not ok:
                    failures.append(msg or chk.message or f"Rule violated: {chk.kind}")
            if failures:
                res = ActionResult(ok=False, action=action, message="; ".join(failures[:2]))
            else:
                res = ActionResult(ok=True, action=action, message="OK")
                for eff in rule.effects:
                    self._apply_effect(eff, action, res)
                if action.action_type == "use":
                    self._handle_use(action, res)
                elif action.action_type == "open":
                    self._handle_open(action, res)
                elif action.action_type == "give":
                    self._handle_give(action, res)
                elif action.action_type == "talk":
                    self._handle_talk(action, res)
                elif action.action_type == "examine":
                    self._handle_examine(action, res)
                elif action.action_type == "accuse":
                    self._handle_accuse(action, res)
                if res.ok:
                    if res.message == "OK":
                        res.message = self._success_message(action)
                    self._check_ending()

        if self.collect_transitions:
            after_facts, after_time = extract_facts(self.state, action)
            self.transitions.append(
                {
                    "action_type": action.action_type,
                    "params": dict(action.params),
                    "ok": res.ok,
                    "before": sorted(before_facts),
                    "after": sorted(after_facts),
                    "before_time": before_time,
                    "after_time": after_time,
                }
            )

        self.state.turn += 1
        self._record(res)
        self._snapshot()
        return res

    def _success_message(self, action: Action) -> str:
        """Render a deterministic fact for simple successful actions.

        This message is consumed by the event log and grounded narrator, so it
        must describe the applied post-action state rather than a generic OK.
        """
        if action.action_type == "move":
            destination = self.state.entity(action.params["to"])
            return f"You move to the {destination.name}."
        if action.action_type == "take":
            item = self.state.entity(action.params["item"])
            return f"You take the {item.name}."
        if action.action_type == "give":
            item = self.state.entity(action.params["item"])
            recipient = self.state.entity(action.params["recipient"])
            return f"You give the {item.name} to {recipient.name}."
        if action.action_type == "wait":
            return "Time passes."
        return f"The {action.action_type} action succeeds."

    def _eval_check(self, chk: Check, action: Action) -> tuple[bool, str | None]:
        st = self.state
        subj = self.resolve_ref(chk.subject, action)
        tgt = self.resolve_ref(chk.target, action) if chk.target else None

        if chk.kind == "here":
            if subj is None or tgt is None:
                return False, "I don't know what that refers to."
            return st.entity(subj).location_id == tgt, None
        if chk.kind == "same_location":
            if subj is None or tgt is None:
                return False, "I don't know what that refers to."
            a, b = st.entity(subj), st.entity(tgt)
            ok = (
                a.location_id is not None
                and a.location_id == b.location_id
                and a.location_id != INVENTORY_ID
            )
            return ok, None
        if chk.kind == "inventory":
            ent = st.entity(subj)
            return ent.owner_id == tgt and ent.location_id == INVENTORY_ID, None
        if chk.kind == "not_owned":
            return st.entity(subj).owner_id is None, None
        if chk.kind == "connected":
            loc = st.entity(subj)
            return tgt in loc.attributes.get("connections", []), None
        if chk.kind == "accessible":
            if subj is None or tgt is None or subj not in st.entities or tgt not in st.entities:
                return False, "I don't know what that refers to."
            item, actor = st.entity(subj), st.entity(tgt)
            return (
                item.location_id == actor.location_id
                or (item.owner_id == tgt and item.location_id == INVENTORY_ID)
            ), None
        if chk.kind == "attribute":
            return st.entity(subj).attributes.get(chk.attr) == chk.value, None
        if chk.kind == "flag":
            return st.flags.get(chk.attr) == chk.value, None
        return False, f"Unknown check: {chk.kind}"

    def _apply_effect(self, eff: Effect, action: Action, res: ActionResult) -> None:
        subj = self.resolve_ref(eff.subject, action)
        tgt = self.resolve_ref(eff.target, action) if eff.target else None
        if eff.kind == "set_location":
            self.state.entity(subj).location_id = tgt
        elif eff.kind == "set_owner":
            ent = self.state.entity(subj)
            ent.owner_id = tgt
            ent.location_id = INVENTORY_ID
        elif eff.kind == "set_attribute":
            self.state.entity(subj).attributes[eff.attr] = eff.value
        elif eff.kind == "set_flag":
            self.state.flags[eff.attr] = eff.value
        elif eff.kind == "advance_time":
            self.state.time += int(eff.value or 1)
        elif eff.kind == "message":
            res.effects.append(str(eff.value))
        res.effects.append(eff.kind)

    # ------------------------------------------------------------------
    # World-specific composite action handlers
    # ------------------------------------------------------------------
    def _handle_use(self, action: Action, res: ActionResult) -> None:
        item = self.state.entity(action.params["item"])
        target_id = action.params.get("target")
        if not target_id:
            res.ok = False
            res.message = "Use it on what?"
            return
        target = self.state.entity(target_id)
        unlock_key = target.attributes.get("unlock_key")
        if unlock_key and unlock_key == item.id and target.attributes.get("locked"):
            target.attributes["locked"] = False
            res.effects.append(f"unlocked:{target_id}")
            res.message = f"The {target.name} clicks open."
            return
        if target.attributes.get("fill_with") == item.id and not target.attributes.get(
            "filled"
        ):
            target.attributes["filled"] = True
            res.effects.append(f"filled:{target_id}")
            res.message = f"You fill the {target.name} with the {item.name}."
            return
        if target.attributes.get("light_with") == item.id and target.attributes.get(
            "filled"
        ):
            target.attributes["lit"] = True
            self.state.flags["lighthouse_lit"] = True
            res.effects.append(f"lit:{target_id}")
            res.message = f"The {target.name} blazes to life!"
            return
        res.ok = False
        res.message = (
            f"Using the {item.name} on the {target.name} doesn't seem to do anything."
        )

    def _handle_open(self, action: Action, res: ActionResult) -> None:
        target = self.state.entity(action.params["target"])
        if target.attributes.get("locked"):
            res.ok = False
            res.message = f"The {target.name} is locked."
            return
        contained = target.attributes.get("contains", [])
        if contained:
            here = self.state.entity(action.actor_id).location_id
            names: list[str] = []
            for cid in contained:
                ent = self.state.entity(cid)
                ent.location_id = here
                ent.owner_id = None
                res.effects.append(f"revealed:{cid}")
                names.append(ent.name)
            target.attributes["contains"] = []
            res.message = (
                "You open the " + target.name + " and find: " + ", ".join(names) + "."
            )
        else:
            res.message = f"The {target.name} is already open."

    def _handle_give(self, action: Action, res: ActionResult) -> None:
        """Gift-driven world effects (e.g. giving the oil can to Mara)."""
        recipient = self.state.entity(action.params["recipient"])
        gift_effects = recipient.attributes.get("gift_effect", {})
        flag = gift_effects.get(action.params["item"])
        if flag:
            self.state.flags[flag] = True
            res.effects.append(f"flag:{flag}")

    def _handle_talk(self, action: Action, res: ActionResult) -> None:
        """Scripted dialogue: the line depends on world flags, never on memory."""
        target = self.state.entity(action.params["target"])
        st = self.state
        script = target.attributes.get("dialogue", {})
        line = None
        for flag in ("learned_secret", "gave_oil"):
            if flag in script and st.flags.get(flag):
                line = script[flag]
                break
        if line is None:
            line = script.get("default", f"{target.name} has nothing to say.")
        res.message = line
        # The reveal: the talk that follows the gift tells the secret, and only
        # afterwards does the flag flip (so the *next* talk shows the new line).
        if (
            action.params["target"] == "mara"
            and st.flags.get("gave_oil")
            and not st.flags.get("learned_secret")
        ):
            st.flags["learned_secret"] = True
        talk_flag = target.attributes.get("talk_flag")
        if talk_flag:
            st.flags[talk_flag] = True
            res.effects.append(f"flag:{talk_flag}")

    def _handle_examine(self, action: Action, res: ActionResult) -> None:
        """Return an authoritative observation without inventing hidden facts."""
        target = self.state.entity(action.params["target"])
        detail = target.attributes.get("examine_text") or target.description
        res.message = f"You examine the {target.name}. {detail}".strip()
        examine_flag = target.attributes.get("examine_flag")
        if examine_flag:
            self.state.flags[examine_flag] = True
            res.effects.append(f"flag:{examine_flag}")

    def _handle_accuse(self, action: Action, res: ActionResult) -> None:
        """Resolve the case only when the configured evidence chain is complete."""
        suspect = self.state.entity(action.params["target"])
        required = list(suspect.attributes.get("accusation_requires", []))
        missing = [flag for flag in required if not self.state.flags.get(flag)]
        if not suspect.attributes.get("culprit"):
            res.message = (
                f"You accuse {suspect.name}, but the confirmed evidence does not support the charge. "
                "The investigation remains open."
            )
            return
        if missing:
            res.message = (
                f"You confront {suspect.name}, but {len(missing)} required evidence link(s) are still missing. "
                "The accusation does not hold."
            )
            return
        self.state.flags["case_solved"] = True
        self.state.flags["accused"] = suspect.id
        res.effects.extend(["flag:case_solved", f"accused:{suspect.id}"])
        res.message = str(
            suspect.attributes.get(
                "confession",
                f"The evidence closes around {suspect.name}. The case is solved.",
            )
        )

    def _check_ending(self) -> bool:
        st = self.state
        if (
            st.flags.get("lighthouse_lit")
            and st.flags.get("learned_secret")
            and st.flags.get("case_solved")
            and not st.flags.get("ending")
        ):
            st.flags["ending"] = True
            return True
        return False

    # ------------------------------------------------------------------
    # History & snapshots
    # ------------------------------------------------------------------
    def _record(self, res: ActionResult) -> None:
        self.history.append(
            EventRecord(
                turn=self.state.turn,
                actor_id=res.action.actor_id,
                action=res.action,
                ok=res.ok,
                message=res.message,
                state_hash=self.state.snapshot_hash(),
            )
        )

    def _snapshot(self) -> None:
        self.snapshots[self.state.turn] = (
            copy.deepcopy(self.state),
            self.state.snapshot_hash(),
        )

    def rollback(self, turn: int) -> None:
        if turn not in self.snapshots:
            raise KeyError(f"No snapshot for turn {turn}")
        self.state = copy.deepcopy(self.snapshots[turn][0])
        self.history = [h for h in self.history if h.turn <= turn]
        for t in [t for t in self.snapshots if t > turn]:
            del self.snapshots[t]

    # ------------------------------------------------------------------
    # Presentation helpers (used by the CLI and, later, by the LLM layer)
    # ------------------------------------------------------------------
    def player_id(self) -> str:
        for e in self.state.entities.values():
            if e.kind == EntityKind.CHARACTER and e.name.lower() in ("you", "player"):
                return e.id
        raise KeyError("No player entity in world")

    def visible_summary(self, actor_id: str) -> str:
        st = self.state
        actor = st.entity(actor_id)
        loc = st.entity(actor.location_id)
        lines = [f"[{loc.name}] {loc.description}"]
        here = actor.location_id
        items = [
            e
            for e in st.entities.values()
            if e.kind == EntityKind.ITEM and e.location_id == here and e.owner_id is None
        ]
        chars = [
            e
            for e in st.entities.values()
            if e.kind == EntityKind.CHARACTER
            and e.location_id == here
            and e.id != actor_id
        ]
        conns = loc.attributes.get("connections", [])
        if chars:
            lines.append("Here: " + ", ".join(c.name for c in chars))
        if items:
            lines.append("You can see: " + ", ".join(i.name for i in items))
        if conns:
            lines.append("Exits: " + ", ".join(st.entity(c).name for c in conns))
        return "\n".join(lines)

    def inventory_summary(self, actor_id: str) -> str:
        st = self.state
        inv = [
            e
            for e in st.entities.values()
            if e.owner_id == actor_id and e.location_id == INVENTORY_ID
        ]
        if not inv:
            return "Your inventory is empty."
        return "Inventory: " + ", ".join(e.name for e in inv)

    def quest_summary(self) -> str:
        st = self.state
        quests = [e for e in st.entities.values() if e.kind == EntityKind.QUEST]
        lines = []
        for q in quests:
            done = bool(st.flags.get(q.attributes.get("flag", "")))
            lines.append(("[x] " if done else "[ ] ") + q.name)
        return "\n".join(lines)
