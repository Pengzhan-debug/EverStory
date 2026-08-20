"""Greedy conjunctive rule induction from (state, action, next-state) traces.

For each action type we learn:
- **preconditions**: a conjunction of predicates that hold in every successful
  transition and exclude every failed one;
- **effects**: predicates consistently added / removed by successful actions.

Composite actions (`use`, `open`) are attribute-driven in the engine, so their
rules are induced per item-target pair rather than globally.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

COMPOSITE_ACTIONS = {"use", "open"}


@dataclass
class LearnedRule:
    action_type: str
    preconditions: list[str] = field(default_factory=list)
    effects_added: list[str] = field(default_factory=list)
    effects_removed: list[str] = field(default_factory=list)
    time_delta: int | None = None
    positives: int = 0
    negatives: int = 0
    pair_rules: dict[str, "LearnedRule"] = field(default_factory=dict)
    pair_key: str | None = field(default=None, init=False)


def _learn_preconditions(
    pos_fact_sets: list[set[str]], neg_fact_sets: list[set[str]]
) -> list[str]:
    """Learn a conjunction that covers all positives and no negatives."""
    if not pos_fact_sets:
        return []
    common = set.intersection(*pos_fact_sets)
    # Drop predicates that hold in every negative too (they don't discriminate)
    # and trivial "actor is somewhere" tautologies. Only predicates whose
    # arguments are all action roles (or the literal "inventory") are kept:
    # incidental scene facts (e.g. "the cliff path is connected from here")
    # cannot help predict the action and would only add noise.
    negs = [set(n) for n in neg_fact_sets]
    candidate = [
        p
        for p in common
        if _all_args_are_roles(p)
        and not p.startswith("at($actor,")
        and (not negs or not all(p in n for n in negs))
    ]
    covered = [i for i, n in enumerate(negs) if set(candidate) <= n]
    while covered:
        pool = set().union(*pos_fact_sets)
        best, best_gain = None, -1
        for p in sorted(pool):
            if p in candidate:
                continue
            gain = sum(1 for i in covered if p not in negs[i])
            if gain > best_gain:
                best, best_gain = p, gain
        if best is None:
            break
        candidate.append(best)
        covered = [i for i in covered if set(candidate) <= negs[i]]
    return sorted(candidate)


def _learn_effects(pos: list[dict]) -> tuple[list[str], list[str], int | None]:
    added_all = [set(t["after"]) - set(t["before"]) for t in pos]
    removed_all = [set(t["before"]) - set(t["after"]) for t in pos]
    # Static world structure (the map, unlock-key wiring) never actually
    # changes; its predicates only flicker because of the state-dependent
    # "$here" token. Keep effects limited to dynamic facts.
    added = {
        p
        for p in (set.intersection(*added_all) if added_all else set())
        if not p.startswith(("connected(", "key_for("))
    }
    removed = {
        p
        for p in (set.intersection(*removed_all) if removed_all else set())
        if not p.startswith(("connected(", "key_for("))
    }
    deltas = {t["after_time"] - t["before_time"] for t in pos}
    time_delta = next(iter(deltas)) if len(deltas) == 1 else None
    return sorted(added), sorted(removed), time_delta


def _all_args_are_roles(predicate: str) -> bool:
    if "(" not in predicate or not predicate.endswith(")"):
        return False
    body = predicate.split("(", 1)[1][:-1]
    args = [a.strip() for a in body.split(",")]
    return all(a.startswith("$") or a == "inventory" for a in args)


def _pair_key(t: dict) -> str:
    item = t["params"].get("item", "")
    target = t["params"].get("target", "")
    return f"{item} -> {target}" if target else item


def _induce_pair_rules(transitions: list[dict]) -> dict[str, LearnedRule]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in transitions:
        groups[_pair_key(t)].append(t)
    out: dict[str, LearnedRule] = {}
    for key, ts in sorted(groups.items()):
        pos = [t for t in ts if t["ok"]]
        neg = [t for t in ts if not t["ok"]]
        pre = _learn_preconditions(
            [set(t["before"]) for t in pos], [set(t["before"]) for t in neg]
        )
        added, removed, tdelta = _learn_effects(pos)
        rule = LearnedRule(
            action_type=ts[0]["action_type"],
            preconditions=pre,
            effects_added=added,
            effects_removed=removed,
            time_delta=tdelta,
            positives=len(pos),
            negatives=len(neg),
        )
        rule.pair_key = key
        out[key] = rule
    return out


def induce(transitions: list[dict]) -> list[LearnedRule]:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for t in transitions:
        by_type[t["action_type"]].append(t)

    rules: list[LearnedRule] = []
    for atype in sorted(by_type):
        ts = by_type[atype]
        pos = [t for t in ts if t["ok"]]
        neg = [t for t in ts if not t["ok"]]
        if atype in COMPOSITE_ACTIONS:
            rules.append(
                LearnedRule(
                    action_type=atype,
                    positives=len(pos),
                    negatives=len(neg),
                    pair_rules=_induce_pair_rules(ts),
                )
            )
        else:
            pre = _learn_preconditions(
                [set(t["before"]) for t in pos],
                [set(t["before"]) for t in neg],
            )
            added, removed, tdelta = _learn_effects(pos)
            rules.append(
                LearnedRule(
                    action_type=atype,
                    preconditions=pre,
                    effects_added=added,
                    effects_removed=removed,
                    time_delta=tdelta,
                    positives=len(pos),
                    negatives=len(neg),
                )
            )
    return rules


def predict(
    rule: LearnedRule, facts, params: dict | None = None
) -> bool:
    if params and rule.pair_rules:
        sub = rule.pair_rules.get(_pair_key({"params": params}))
        if sub is not None:
            return set(sub.preconditions) <= set(facts)
    return set(rule.preconditions) <= set(facts)


def evaluate(rules: list[LearnedRule], transitions: list[dict]) -> dict:
    by_type = {r.action_type: r for r in rules}
    correct = total = 0
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for t in transitions:
        rule = by_type.get(t["action_type"])
        if rule is None:
            continue
        hit = predict(rule, t["before"], t.get("params")) == t["ok"]
        correct += int(hit)
        total += 1
        per_type[t["action_type"]][0] += int(hit)
        per_type[t["action_type"]][1] += 1
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "per_type": dict(per_type),
    }


_REPLACEMENTS = {
    "$actor": "<actor>",
    "$here": "<here>",
    "$item": "<item>",
    "$target": "<target>",
    "$to": "<destination>",
    "$recipient": "<recipient>",
}


def _pretty(pred: str) -> str:
    for key, value in _REPLACEMENTS.items():
        pred = pred.replace(key, value)
    return pred.replace("_", " ")


def _render_effects(rule: LearnedRule) -> str:
    parts = [f"+{_pretty(e)}" for e in rule.effects_added]
    parts += [f"-{_pretty(e)}" for e in rule.effects_removed]
    if rule.time_delta is not None:
        parts.append(f"time +{rule.time_delta}")
    return "; ".join(parts) if parts else "(none)"


def readable(rule: LearnedRule) -> str:
    if rule.pair_rules:
        lines = [
            f"- **{rule.action_type}** (composite; induced per item-target pair):"
        ]
        for key, sub in sorted(rule.pair_rules.items()):
            pre = " ∧ ".join(_pretty(p) for p in sub.preconditions) or "(always valid)"
            lines.append(f"  - `{key}`: valid if [{pre}]; effects: {_render_effects(sub)}")
        return "\n".join(lines)
    pre = " ∧ ".join(_pretty(p) for p in rule.preconditions) or "(always valid)"
    return (
        f"- **{rule.action_type}**: valid if [{pre}]; effects: {_render_effects(rule)}"
    )
