"""Turn pipeline: intent -> engine -> narration -> fact check -> summary."""

from __future__ import annotations

from dataclasses import dataclass, field

from .llm.client import LLMClient
from .llm.intent import parse_actions
from .llm.judge import check_consistency
from .llm.narrator import narrate, narrate_stub
from .memory.context import build_context, summarize
from .models import Action


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

    def process(self, user_text: str) -> TurnResult:
        s = self.session
        actor = s.player_id()
        context = build_context(s, actor, self._event_history, self.summary)

        actions = parse_actions(user_text, context, self.client)
        if not actions and self.client.mode != "stub":
            # One retry: the parser may have failed; insist on valid output.
            actions = parse_actions(
                user_text,
                context + "\n(You must emit at least one valid action.)",
                self.client,
            )

        results = []
        for proposal in actions:
            atype = proposal.get("type", "")
            params = {
                k: str(v) for k, v in (proposal.get("params") or {}).items()
            }
            results.append(
                s.act(Action(action_type=atype, actor_id=actor, params=params))
            )

        if not results:
            return TurnResult(
                narration="I don't understand what you're trying to do.",
                results=[],
                turn=s.state.turn,
                state_hash=s.state.snapshot_hash(),
                summary=self.summary,
            )

        facts = [r.message for r in results]
        events = [f"[turn {s.state.turn}] {r.message}" for r in results]
        self._event_history.extend(events)

        if self.client.mode == "stub":
            narration = narrate_stub(s, results, user_text)
        else:
            narration = narrate(
                self.client,
                context
                + "\n\nPlayer input:\n"
                + user_text
                + "\n\nEngine results:\n"
                + "\n".join(facts),
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
                    )

        if s.state.turn % self.summary_every == 0:
            window = " ".join(self._event_history[-self.summary_every * 2 :])
            self.summary = summarize(self.client, window, self.summary)

        rejected = [r.message for r in results if not r.ok]
        return TurnResult(
            narration=narration,
            results=results,
            turn=s.state.turn,
            state_hash=s.state.snapshot_hash(),
            rejected=rejected,
            summary=self.summary,
        )
