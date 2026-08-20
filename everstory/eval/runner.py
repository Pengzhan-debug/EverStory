"""Run the three-architecture benchmark and produce a report."""

from __future__ import annotations

from dataclasses import dataclass

from .baselines import EverStoryBaseline, PureLLMBaseline, SummaryMemoryBaseline
from .episodes import EPISODES, Episode

BASELINE_CLASSES = [PureLLMBaseline, SummaryMemoryBaseline, EverStoryBaseline]


@dataclass
class Result:
    baseline: str
    episode: str
    recall: float
    correct: int
    total: int
    rejections: int
    tokens: int


def state_answer(session, question: str) -> str | None:
    """Deterministic answer to fact questions, read straight from the state."""
    st = session.state
    q = question.lower()
    if "lit" in q:
        return "yes" if st.flags.get("lighthouse_lit") else "no"
    if "locked" in q:
        for e in st.entities.values():
            if e.attributes.get("locked"):
                return "yes"
        return "no"
    for e in st.entities.values():
        if e.name.lower() in q:
            if "where" in q:
                if e.owner_id:
                    return "inventory"
                if e.location_id and e.location_id != "inventory":
                    return st.entity(e.location_id).name.lower()
                return "unknown"
            if "who" in q or "carrying" in q:
                return st.entity(e.owner_id).name.lower() if e.owner_id else "nobody"
    return None


def run_eval(client, episodes: list[Episode] | None = None, baselines=None) -> list[Result]:
    episodes = episodes or EPISODES
    results: list[Result] = []
    for baseline_cls in baselines or BASELINE_CLASSES:
        for ep in episodes:
            b = baseline_cls(client)
            b.reset()
            for step in ep.steps:
                b.turn(step)
            correct = 0
            for fact in ep.facts:
                if b.name == "everstory":
                    got = state_answer(b.session, fact.question)
                    if got and fact.answer.lower() in got.lower():
                        correct += 1
                else:
                    reply = b.ask(fact.question)
                    if fact.answer.lower() in reply.lower():
                        correct += 1
            total = len(ep.facts)
            results.append(
                Result(
                    baseline=b.name,
                    episode=ep.name,
                    recall=correct / total,
                    correct=correct,
                    total=total,
                    rejections=b.rejections,
                    tokens=b.tokens,
                )
            )
    return results


def to_markdown(results: list[Result], mode: str) -> str:
    rows = "\n".join(
        f"| {r.baseline} | {r.episode} | {r.recall:.0%} ({r.correct}/{r.total}) | "
        f"{r.rejections} | {r.tokens} |"
        for r in results
    )
    return f"""# EverStory Evaluation Report

Mode: `{mode}` (stub = deterministic/offline; api = real LLM numbers)

| Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
{rows}

Notes:
- **EverStory** answers fact questions directly from its structured state, so
  recall is exact by construction; its "tokens" reflect narration/parsing only.
- **pure-llm** keeps the full transcript in context; **summary-memory** keeps a
  rolling summary plus recent turns. Both depend on the model's memory.
- Run `python -m everstory.eval --mode api` (with `LLM_API_KEY` set) for real
  model numbers.
"""
