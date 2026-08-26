"""Turn pipeline: intent -> engine -> narration -> fact check -> summary."""

from __future__ import annotations

from dataclasses import dataclass, field

from .llm.client import LLMClient
from .llm.dialogue import npc_reply, npc_reply_stub
from .llm.dialogue import npc_reply_stream
from .llm.intent import parse_actions
from .llm.judge import check_consistency
from .llm.narrator import (
    chat_reply,
    chat_reply_stub,
    chat_reply_stream,
    narrate,
    narrate_stub,
    narrate_stream,
)
from .memory.context import build_context, summarize
from .models import Action, ActionResult


TEAM_APPROVAL_ACTIONS = {"examine", "accuse"}


@dataclass
class TurnResult:
    narration: str
    results: list
    turn: int
    state_hash: str
    rejected: list[str] = field(default_factory=list)
    summary: str = ""


class TurnPipeline:
    """Coordinates one interactive turn end to end."""

    def __init__(
        self,
        session,
        client: LLMClient | None = None,
        fact_check: bool = True,
        summary_every: int = 5,
    ) -> None:
        self.session = session
        self.client = client or LLMClient()
        self.fact_check = fact_check
        self.summary_every = summary_every
        self.summary = ""
        self._event_history: list[str] = []
        self.dialogue_history: list[dict] = []
        self.transcript: list[dict] = []

    def _nearby_character(self):
        """The first character standing in the same location as the player."""
        s = self.session
        actor = s.player_id()
        player = s.state.entity(actor)
        for e in s.state.entities.values():
            if (
                e.kind.value == "character"
                and e.id != actor
                and e.location_id == player.location_id
            ):
                return e
        return None

    def _remember_dialogue(self, speaker: str, text: str) -> None:
        self.dialogue_history.append({"speaker": speaker, "text": text})
        del self.dialogue_history[:-6]

    def _remember_transcript(self, user_text: str, narration: str, character=None) -> None:
        assistant = {
            "role": "assistant",
            "text": narration,
            "speaker_id": character.id if character is not None else "world_narrator",
            "speaker_name": character.name if character is not None else "World Narrator",
            "speaker_role": "Character Dialogue" if character is not None else "Live Narration",
        }
        self.transcript.extend(
            [
                {"role": "user", "text": user_text, "command": user_text},
                assistant,
            ]
        )
        del self.transcript[:-60]

    def memory_payload(self) -> dict:
        return {
            "version": 1,
            "summary": self.summary,
            "event_history": list(self._event_history[-40:]),
            "dialogue_history": list(self.dialogue_history[-6:]),
            "transcript": list(self.transcript[-60:]),
        }

    def restore_memory(self, data: dict | None) -> None:
        if not isinstance(data, dict):
            return
        self.summary = str(data.get("summary") or "")
        self._event_history = [
            str(item) for item in data.get("event_history", []) if isinstance(item, str)
        ][-40:]
        self.dialogue_history = [
            dict(item) for item in data.get("dialogue_history", []) if isinstance(item, dict)
        ][-6:]
        self.transcript = [
            dict(item)
            for item in data.get("transcript", [])
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("text"), str)
        ][-60:]

    def _apply_proposal(self, actor: str, proposal: dict, locale: str) -> ActionResult:
        """Keep authoritative evidence work inside the investigation team loop."""
        action = Action(
            action_type=proposal.get("type", ""),
            actor_id=actor,
            params={
                key: str(value)
                for key, value in (proposal.get("params") or {}).items()
            },
        )
        if action.action_type in TEAM_APPROVAL_ACTIONS:
            message = (
                "关键证据必须由联合调查室复核。请让艾瑞丝·维尔检查证物，或让黑尔主管提出正式指控，并在案件板中批准。"
                if locale == "zh-CN"
                else "Authoritative evidence must be reviewed in the Investigation Room. Ask Iris Vale to examine the item or Director Hale to propose the accusation, then approve it on the case board."
            )
            return ActionResult(ok=False, action=action, message=message)
        return self.session.act(action)

    def _emit_text(self, chunks, holder: dict):
        """Yield text deltas while accumulating the full reply."""
        full = ""
        for chunk in chunks:
            if chunk:
                full += chunk
                yield {"type": "text", "delta": chunk}
        holder["text"] = full

    def _done_event(self, narration, results, rejected, world_renderer=None) -> dict:
        ev = {
            "type": "done",
            "reply": narration,
            "turn": self.session.state.turn,
            "state_hash": self.session.state.snapshot_hash(),
            "events": [
                {"type": r.action.action_type, "ok": r.ok, "message": r.message}
                for r in results
            ],
            "rejected": rejected,
            "summary": self.summary,
        }
        if world_renderer is not None:
            ev["world"] = world_renderer(self.session)
        return ev

    def process_stream(self, user_text: str, world_renderer=None, locale: str = "en"):
        """Like process(), but streams the reply text for a chat-like UI."""
        s = self.session
        actor = s.player_id()
        context = build_context(s, actor, self._event_history, self.summary)

        actions = parse_actions(user_text, context, self.client)

        if not actions:
            character = self._nearby_character()
            if character is not None:
                if self.client.mode == "stub":
                    full = npc_reply_stub(character, user_text, locale=locale)
                    yield {"type": "text", "delta": full}
                else:
                    holder = {}
                    for ev in self._emit_text(
                        npc_reply_stream(
                            self.client,
                            character,
                            context,
                            user_text,
                            self.dialogue_history,
                            locale=locale,
                        ),
                        holder,
                    ):
                        yield ev
                    full = holder["text"]
                self._remember_dialogue("you", user_text)
                self._remember_dialogue(character.name, full)
            else:
                if self.client.mode == "stub":
                    full = chat_reply_stub(user_text, locale=locale)
                    yield {"type": "text", "delta": full}
                else:
                    holder = {}
                    for ev in self._emit_text(
                        chat_reply_stream(
                            self.client,
                            context + "\n\nPlayer says:\n" + user_text,
                            user_text,
                            locale=locale,
                        ),
                        holder,
                    ):
                        yield ev
                    full = holder["text"]
            self._remember_transcript(user_text, full, character)
            yield self._done_event(full, [], [], world_renderer=world_renderer)
            return

        results = [self._apply_proposal(actor, proposal, locale) for proposal in actions]

        facts = [r.message for r in results]
        events = [f"[turn {s.state.turn}] {r.message}" for r in results]
        self._event_history.extend(events)
        # Narration must see the authoritative post-action world. Using the
        # pre-action context here can make a successful move describe the old
        # location even though the state transition was correct.
        context = build_context(s, actor, self._event_history, self.summary)

        talks = [r for r in results if r.ok and r.action.action_type == "talk"]
        if talks:
            t = talks[0]
            target_id = t.action.params.get("target")
            target = s.state.entity(target_id) if target_id else None
            canonical = t.message or ""
            if target is not None:
                if self.client.mode == "stub":
                    full = npc_reply_stub(target, user_text, canonical, locale=locale)
                    yield {"type": "text", "delta": full}
                else:
                    holder = {}
                    for ev in self._emit_text(
                        npc_reply_stream(
                            self.client,
                            target,
                            context + "\n\nPlayer says:\n" + user_text,
                            user_text,
                            self.dialogue_history,
                            canonical,
                            locale=locale,
                        ),
                        holder,
                    ):
                        yield ev
                    full = holder["text"]
                self._remember_dialogue("you", user_text)
                self._remember_dialogue(target.name, full)
            else:
                full = narrate_stub(s, results, user_text, locale=locale)
                yield {"type": "text", "delta": full}
        elif self.client.mode == "stub":
            full = narrate_stub(s, results, user_text, locale=locale)
            yield {"type": "text", "delta": full}
        else:
            holder = {}
            for ev in self._emit_text(
                narrate_stream(
                    self.client,
                    context
                    + "\n\nPlayer input:\n"
                    + user_text
                    + "\n\nEngine results:\n"
                    + "\n".join(facts),
                    locale=locale,
                ),
                holder,
            ):
                yield ev
            full = holder["text"]
            if self.fact_check:
                ok, issues = check_consistency(self.client, full, facts)
                if not ok:
                    full = narrate(
                        self.client,
                        context
                        + "\n\nEngine results:\n"
                        + "\n".join(facts)
                        + "\n\nYour previous narration was flagged inconsistent: "
                        + "; ".join(issues)
                        + ". Rewrite it to match the facts exactly.",
                        locale=locale,
                    )
                    yield {"type": "replace", "text": full}

        if s.state.turn % self.summary_every == 0:
            window = " ".join(self._event_history[-self.summary_every * 2 :])
            self.summary = summarize(self.client, window, self.summary)

        rejected = [r.message for r in results if not r.ok]
        transcript_character = target if talks and target is not None else None
        self._remember_transcript(user_text, full, transcript_character)
        yield self._done_event(full, results, rejected, world_renderer=world_renderer)

    def process(self, user_text: str, locale: str = "en") -> TurnResult:
        s = self.session
        actor = s.player_id()
        context = build_context(s, actor, self._event_history, self.summary)

        actions = parse_actions(user_text, context, self.client)

        # Pure conversation (greeting, question, small talk): reply in character
        # without touching the world. The engine stays the source of truth.
        if not actions:
            character = self._nearby_character()
            if character is not None:
                # Someone is here: hold a real in-character conversation.
                if self.client.mode == "stub":
                    narration = npc_reply_stub(character, user_text, locale=locale)
                else:
                    narration = npc_reply(
                        self.client,
                        character,
                        context,
                        user_text,
                        self.dialogue_history,
                        locale=locale,
                    )
                self._remember_dialogue("you", user_text)
                self._remember_dialogue(character.name, narration)
            elif self.client.mode == "stub":
                narration = chat_reply_stub(user_text, locale=locale)
            else:
                narration = chat_reply(
                    self.client,
                    context + "\n\nPlayer says:\n" + user_text,
                    user_text,
                    locale=locale,
                )
            self._remember_transcript(user_text, narration, character)
            return TurnResult(
                narration=narration,
                results=[],
                turn=s.state.turn,
                state_hash=s.state.snapshot_hash(),
                summary=self.summary,
            )

        results = [self._apply_proposal(actor, proposal, locale) for proposal in actions]

        facts = [r.message for r in results]
        events = [f"[turn {s.state.turn}] {r.message}" for r in results]
        self._event_history.extend(events)
        context = build_context(s, actor, self._event_history, self.summary)

        talks = [r for r in results if r.ok and r.action.action_type == "talk"]
        if talks:
            # A successful talk: let the NPC answer in character, grounded in
            # the canonical scripted line the engine just selected.
            t = talks[0]
            target_id = t.action.params.get("target")
            target = s.state.entity(target_id) if target_id else None
            canonical = t.message or ""
            if target is not None:
                if self.client.mode == "stub":
                    narration = npc_reply_stub(target, user_text, canonical, locale=locale)
                else:
                    narration = npc_reply(
                        self.client,
                        target,
                        context + "\n\nPlayer says:\n" + user_text,
                        user_text,
                        self.dialogue_history,
                        canonical,
                        locale=locale,
                    )
                self._remember_dialogue("you", user_text)
                self._remember_dialogue(target.name, narration)
            else:
                narration = (
                    narrate_stub(s, results, user_text, locale=locale)
                    if self.client.mode == "stub"
                    else narrate(
                        self.client,
                        context
                        + "\n\nPlayer input:\n"
                        + user_text
                        + "\n\nEngine results:\n"
                        + "\n".join(facts),
                        locale=locale,
                    )
                )
        elif self.client.mode == "stub":
            narration = narrate_stub(s, results, user_text, locale=locale)
        else:
            narration = narrate(
                self.client,
                context
                + "\n\nPlayer input:\n"
                + user_text
                + "\n\nEngine results:\n"
                + "\n".join(facts),
                locale=locale,
            )
            if self.fact_check:
                for _ in range(2):
                    ok, issues = check_consistency(self.client, narration, facts)
                    if ok:
                        break
                    narration = narrate(
                        self.client,
                        context
                        + "\n\nEngine results:\n"
                        + "\n".join(facts)
                        + "\n\nYour previous narration was flagged inconsistent: "
                        + "; ".join(issues)
                        + ". Rewrite it to match the facts exactly.",
                        locale=locale,
                    )

        if s.state.turn % self.summary_every == 0:
            window = " ".join(self._event_history[-self.summary_every * 2 :])
            self.summary = summarize(self.client, window, self.summary)

        rejected = [r.message for r in results if not r.ok]
        transcript_character = target if talks and target is not None else None
        self._remember_transcript(user_text, narration, transcript_character)
        return TurnResult(
            narration=narration,
            results=results,
            turn=s.state.turn,
            state_hash=s.state.snapshot_hash(),
            rejected=rejected,
            summary=self.summary,
        )
