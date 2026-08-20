"""Three architectures measured by the harness."""

from __future__ import annotations

from ..engine import WorldSession
from ..memory.context import build_context, summarize
from ..pipeline import TurnPipeline
from ..worlds import load_world

PURE_SYSTEM = (
    "You are playing a text-adventure game called The Lost Lighthouse. "
    "Track the world state yourself: locations, items, ownership, locks, and the quest. "
    "Respond in character as the game narrator in 1-3 sentences. "
    "Never mention that you are an AI."
)


class Baseline:
    name = "base"

    def __init__(self, client) -> None:
        self.client = client
        self.tokens = 0
        self.rejections = 0

    def reset(self) -> None:
        raise NotImplementedError

    def turn(self, text: str) -> str:
        raise NotImplementedError

    def ask(self, question: str) -> str:
        raise NotImplementedError

    def _count_tokens(self) -> None:
        self.tokens += sum(self.client.last_usage.values())


class PureLLMBaseline(Baseline):
    """No structured state: the model must remember everything itself."""

    name = "pure-llm"

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": PURE_SYSTEM}]

    def turn(self, text: str) -> str:
        self.messages.append({"role": "user", "content": text})
        reply = self.client.chat(self.messages, model=self.client.cheap_model)
        self.messages.append({"role": "assistant", "content": reply})
        self._count_tokens()
        return reply

    def ask(self, question: str) -> str:
        reply = self.client.chat(
            self.messages
            + [
                {
                    "role": "user",
                    "content": (
                        "QUESTION (answer briefly, from the game state you remember): "
                        + question
                    ),
                }
            ],
            model=self.client.strong_model,
        )
        self._count_tokens()
        return reply


class SummaryMemoryBaseline(Baseline):
    """Rolling LLM summary + recent turns, but still no structured state."""

    name = "summary-memory"

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": PURE_SYSTEM}]
        self.summary = ""
        self._turns: list[tuple[str, str]] = []

    def _context(self) -> str:
        recent = "\n".join(f"{role}: {text}" for role, text in self._turns[-4:])
        return (
            f"Summary so far: {self.summary or '(none)'}\n\nRecent:\n{recent}"
        )

    def turn(self, text: str) -> str:
        self._turns.append(("user", text))
        context = self._context()
        self.messages = [
            {"role": "system", "content": PURE_SYSTEM},
            {"role": "user", "content": context},
        ]
        reply = self.client.chat(self.messages, model=self.client.cheap_model)
        self._turns.append(("assistant", reply))
        self._count_tokens()
        if len(self._turns) >= 6:
            window = " ".join(t for _, t in self._turns[-6:])
            self.summary = summarize(self.client, window, self.summary)
            self._turns = self._turns[-4:]
        return reply

    def ask(self, question: str) -> str:
        context = self._context()
        reply = self.client.chat(
            [
                {"role": "system", "content": PURE_SYSTEM},
                {
                    "role": "user",
                    "content": context + "\n\nQUESTION (answer briefly): " + question,
                },
            ],
            model=self.client.strong_model,
        )
        self._count_tokens()
        return reply


class EverStoryBaseline(Baseline):
    """Structured state machine + grounded narration (the EverStory design)."""

    name = "everstory"

    def reset(self) -> None:
        self.session = WorldSession(load_world("lost_lighthouse"))
        self.pipeline = TurnPipeline(self.session, self.client, fact_check=False)

    def turn(self, text: str) -> str:
        res = self.pipeline.process(text)
        self.rejections += len(res.rejected)
        self._count_tokens()
        return res.narration

    def ask(self, question: str) -> str:
        # EverStory answers memory questions directly from the structured state.
        ctx = build_context(self.session, self.session.player_id(), [])
        reply = self.client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer the question using ONLY the world facts provided. "
                        "If the facts don't say, answer 'unknown'."
                    ),
                },
                {"role": "user", "content": ctx + "\n\nQuestion: " + question},
            ],
            model=self.client.strong_model,
        )
        self._count_tokens()
        return reply
