"""CLI: induce world-dynamics rules from interaction trajectories.

Usage: python -m everstory.learn [--out docs/learned-rules.md]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..commands import parse_structured
from ..engine import WorldSession
from ..eval.episodes import EPISODES
from ..models import Action
from ..trajectory import extract_facts
from ..worlds import load_world
from .inducer import evaluate, induce, predict, readable

FAILURE_STEPS = [
    "move to cave",            # not connected from the cottage
    "open chest",              # chest is not here
    "take rusty key",          # key is not here
    "use flint on lantern",    # not owned (and lantern not filled)
    "give oil can to mara",    # not owned
]


def play_episode(episode) -> WorldSession:
    session = WorldSession(load_world("lost_lighthouse"), collect_transitions=True)
    for step in episode.steps:
        for proposal in parse_structured(step):
            session.act(
                Action(
                    action_type=proposal["type"],
                    actor_id=session.player_id(),
                    params={k: str(v) for k, v in (proposal.get("params") or {}).items()},
                )
            )
    return session


def play_failures() -> list[dict]:
    """Deliberately failed actions -> negative examples for induction."""
    session = WorldSession(load_world("lost_lighthouse"), collect_transitions=True)
    for step in FAILURE_STEPS:
        for proposal in parse_structured(step):
            session.act(
                Action(
                    action_type=proposal["type"],
                    actor_id=session.player_id(),
                    params={k: str(v) for k, v in (proposal.get("params") or {}).items()},
                )
            )
    return session.transitions


def collect(episodes, include_failures: bool = True) -> list[dict]:
    transitions: list[dict] = []
    for ep in episodes:
        transitions.extend(play_episode(ep).transitions)
    if include_failures:
        transitions.extend(play_failures())
    return transitions


def counterfactual_checks(rules) -> list[tuple[str, bool, str]]:
    by_type = {r.action_type: r for r in rules}
    session = WorldSession(load_world("lost_lighthouse"))
    actor = session.player_id()
    checks = []

    take = Action("take", actor, {"item": "rusty_key"})
    facts, _ = extract_facts(session.state, take)
    checks.append(
        (
            "take the rusty key while standing in the cottage",
            predict(by_type["take"], facts, take.params),
            "expected False (the key is in the sea cave)",
        )
    )

    move = Action("move", actor, {"to": "dock"})
    facts2, _ = extract_facts(session.state, move)
    checks.append(
        (
            "move to the dock from the cottage",
            predict(by_type["move"], facts2, move.params),
            "expected True (the dock is connected)",
        )
    )
    return checks


def render_report(rules, eval_all, eval_ho, checks) -> str:
    lines = [
        "# EverStory — Symbolic World-Model Induction",
        "",
        "Dynamics rules are **learned from interaction trajectories** "
        "`(state, action, next-state)`, not written by hand. Predicates are "
        "abstracted over action roles (`<item>`, `<target>`, `<destination>`, ...) "
        "so rules generalize across entities.",
        "",
        "## Learned rules",
        "",
    ]
    lines += [readable(r) for r in rules]
    lines += [
        "",
        "## Prediction accuracy",
        "",
        f"- **All data**: {eval_all['correct']}/{eval_all['total']} "
        f"({eval_all['accuracy']:.1%}) transitions predicted correctly.",
        f"- **Held-out episode** (light_the_lighthouse, trained only on the other "
        f"two): {eval_ho['correct']}/{eval_ho['total']} ({eval_ho['accuracy']:.1%}).",
        "",
        "Per action type (all data):",
        "",
        "| Action | correct / total |",
        "| --- | --- |",
    ]
    for atype, (c, t) in sorted(eval_all["per_type"].items()):
        lines.append(f"| `{atype}` | {c}/{t} |")
    lines += [
        "",
        "## Counterfactual checks (predictions on a fresh world)",
        "",
    ]
    for desc, predicted, expected in checks:
        mark = "✓" if predicted == ("False" not in expected) else "?"
        lines.append(f"- {desc}: **{predicted}** ({expected})")
    lines += [
        "",
        "## Limitations (honest)",
        "",
        "- The inducer learns **necessary conditions**: preconditions are the "
        "conjunction that separates observed successes from observed failures. "
        "Rarely-exercised preconditions may be missing.",
        "- Effects that touch entities outside the action's params (e.g. `open` "
        "revealing the flint) stay concrete rather than abstracted.",
        "- `use`/`open` are attribute-driven composite handlers, so their rules "
        "are induced per item-target pair instead of one global rule.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Induce world rules from trajectories.")
    parser.add_argument("--out", default="docs/learned-rules.md")
    args = parser.parse_args()

    all_transitions = collect(EPISODES)
    rules = induce(all_transitions)
    eval_all = evaluate(rules, all_transitions)

    # Held-out: train on the first two episodes, test on the third.
    train_transitions = collect(EPISODES[:2])
    test_transitions = collect(EPISODES[2:], include_failures=False)
    rules_ho = induce(train_transitions)
    eval_ho = evaluate(rules_ho, test_transitions)

    checks = counterfactual_checks(rules)
    markdown = render_report(rules, eval_all, eval_ho, checks)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
