"""Run the three-architecture benchmark and produce a report."""

from __future__ import annotations

from dataclasses import dataclass

from .baselines import EverStoryBaseline, PureLLMBaseline, SummaryMemoryBaseline
from .episodes import EPISODES, Episode, long_wander

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
    provider: str = "default"


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


def run_eval(
    client,
    episodes: list[Episode] | None = None,
    baselines=None,
    provider: str = "default",
) -> list[Result]:
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
                    provider=provider,
                )
            )
    return results


def to_markdown(results: list[Result], mode: str) -> str:
    rows = "\n".join(
        f"| {r.provider} | {r.baseline} | {r.episode} | {r.recall:.0%} ({r.correct}/{r.total}) | "
        f"{r.rejections} | {r.tokens} |"
        for r in results
    )
    agg: dict[tuple[str, str], dict] = {}
    for r in results:
        key = (r.provider, r.baseline)
        agg.setdefault(key, {"recall": 0.0, "n": 0, "tokens": 0})
        agg[key]["recall"] += r.recall
        agg[key]["n"] += 1
        agg[key]["tokens"] += r.tokens
    summary = "\n".join(
        f"| {provider} | {baseline} | {v['recall'] / v['n']:.1%} | {v['tokens']} |"
        for (provider, baseline), v in sorted(agg.items())
    )
    return f"""# EverStory Evaluation Report

Mode: `{mode}` (stub = deterministic/offline; api = real LLM numbers)

| Provider | Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
{rows}

## Provider summary (average recall)

| Provider | Baseline | Avg recall | Tokens |
| --- | --- | --- | --- |
{summary}

Notes:
- **EverStory** answers fact questions directly from its structured state, so
  recall is exact by construction; its "tokens" reflect narration/parsing only.
- **pure-llm** keeps the full transcript in context; **summary-memory** keeps a
  rolling summary plus recent turns. Both depend on the model's memory.
- Configure `LLM_STRONG_*` / `LLM_CHEAP_*` in `.env` (each role may use a
  different vendor) and run `python -m everstory.eval --mode api` for real
  model numbers.
"""


def run_long_eval(
    client,
    horizon: int = 60,
    baselines=None,
    provider: str = "default",
    checkpoints: list[int] | None = None,
    contradiction_every: int = 0,
) -> list[dict]:
    """Long-horizon memory decay + optional contradiction rate per baseline."""
    episode = long_wander(horizon)
    cps = checkpoints or [horizon // 3, horizon * 2 // 3, horizon]
    cps = sorted(set(c for c in cps if 0 < c <= horizon))
    out: list[dict] = []
    for baseline_cls in baselines or BASELINE_CLASSES:
        b = baseline_cls(client)
        b.reset()
        replies: list[str] = []
        checkpoint_recall: dict[int, float] = {}
        for step, text in enumerate(episode.steps, start=1):
            replies.append(b.turn(text))
            if step in cps:
                correct = 0
                for fact in episode.facts:
                    if b.name == "everstory":
                        got = state_answer(b.session, fact.question)
                        hit = bool(got) and fact.answer.lower() in got.lower()
                    else:
                        hit = fact.answer.lower() in b.ask(fact.question).lower()
                    correct += int(hit)
                checkpoint_recall[step] = correct / len(episode.facts)
        contradictions = None
        if contradiction_every and client.mode != "stub":
            contradictions = _pairwise_contradictions(
                client, replies, every=contradiction_every
            )
        out.append(
            {
                "baseline": b.name,
                "provider": provider,
                "checkpoints": checkpoint_recall,
                "rejections": b.rejections,
                "tokens": b.tokens,
                "contradictions": contradictions,
            }
        )
    return out


def _pairwise_contradictions(client, replies: list[str], every: int = 5) -> float | None:
    import json

    flagged = total = 0
    for i in range(0, len(replies) - 1, every):
        content = client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Do these two consecutive game narrations contradict each "
                        "other? Reply JSON only: {\"contradiction\": true|false}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"1: {replies[i]}\n\n2: {replies[i + 1]}",
                },
            ],
            model=client.strong_model,
            json_mode=True,
        )
        try:
            contrad = bool(json.loads(content).get("contradiction", False))
        except json.JSONDecodeError:
            contrad = False
        flagged += int(contrad)
        total += 1
    return flagged / total if total else None


def to_long_markdown(results: list[dict]) -> str:
    lines = [
        "## Long-horizon memory decay",
        "",
        "Same world facts asked at checkpoints while wandering for many turns. "
        "Facts never change in this episode, so recall loss is purely a "
        "memory/architecture effect.",
        "",
        "| Baseline | Provider | Checkpoint recall | Tokens | Contradictions |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        recall = ", ".join(
            f"@{t}: {v:.0%}" for t, v in sorted(r["checkpoints"].items())
        )
        contrad = (
            f"{r['contradictions']:.1%}" if r["contradictions"] is not None else "n/a"
        )
        lines.append(
            f"| {r['baseline']} | {r['provider']} | {recall} | "
            f"{r['tokens']} | {contrad} |"
        )
    lines += [
        "",
        "- Contradiction rate: LLM-judge on consecutive narrations (skipped in "
        "stub mode; enable with `--contradictions`).",
        "",
    ]
    return "\n".join(lines)
