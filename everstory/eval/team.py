"""Deterministic multi-agent investigation benchmark.

The benchmark measures the boundary between probabilistic discussion and the
authoritative world engine. It runs offline in stub mode and records real
per-agent latency/token usage when an API client is supplied.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass

from ..agents import TeamChatSession
from ..engine import WorldSession
from ..models import Action
from ..worlds import load_world


@dataclass
class TeamEvalResult:
    provider: str
    proposal_accuracy: float
    proposals_correct: int
    proposals_total: int
    approval_success: float
    approvals_ok: int
    approvals_total: int
    unauthorized_mutations: int
    stale_task_blocked: bool
    evidence_grounding: float
    grounded_evidence: int
    evidence_total: int
    challenge_messages: int
    structured_message_coverage: float
    evidence_linkage: float
    cross_agent_reply_links: int
    message_efficiency: float
    case_solved: bool
    memory_roundtrip: bool
    memory_messages: int
    memory_tasks: int
    memory_evidence: int
    memory_bytes: int
    calls: int
    prompt_tokens: int
    completion_tokens: int
    average_latency_ms: int
    per_agent: dict[str, dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _world_view(session: WorldSession) -> dict:
    state = session.state
    actor = state.entity(session.player_id())
    location = state.entity(actor.location_id)
    characters = [
        {"id": entity.id, "name": entity.name, "description": entity.description}
        for entity in state.entities.values()
        if entity.kind.value == "character"
        and entity.id != actor.id
        and entity.location_id == location.id
    ]
    items = [
        {"id": entity.id, "name": entity.name, "description": entity.description}
        for entity in state.entities.values()
        if entity.kind.value == "item"
        and entity.location_id == location.id
        and entity.owner_id is None
    ]
    exits = [
        {"id": entity_id, "name": state.entity(entity_id).name}
        for entity_id in location.attributes.get("connections", [])
    ]
    quests = [
        entity
        for entity in state.entities.values()
        if entity.kind.value == "quest"
        and not state.flags.get(entity.attributes.get("flag", ""))
    ]
    return {
        "turn": state.turn,
        "history": [
            {"turn": event.turn, "ok": event.ok, "message": event.message}
            for event in session.history
        ],
        "scene": {
            "location": {
                "id": location.id,
                "name": location.name,
                "description": location.description,
            },
            "characters": characters,
            "items": items,
            "exits": exits,
            "objective": quests[0].name if quests else "Follow the evidence",
        },
    }


def _executor(session: WorldSession):
    def execute(spec: dict) -> tuple[dict, dict]:
        result = session.act(
            Action(spec["type"], session.player_id(), dict(spec.get("params") or {}))
        )
        return (
            {
                "type": result.action.action_type,
                "ok": result.ok,
                "message": result.message,
                "effects": list(result.effects),
            },
            _world_view(session),
        )

    return execute


def run_team_eval(client, provider: str = "default") -> TeamEvalResult:
    history_start = len(client.call_history)
    session = WorldSession(load_world("lost_lighthouse"))
    team = TeamChatSession()
    correct = total = approvals_ok = approvals_total = unauthorized = 0

    def propose(text: str, expected: dict) -> dict:
        nonlocal correct, total, unauthorized
        before_hash = session.state.snapshot_hash()
        before_turn = session.state.turn
        payload = team.post(
            text,
            session.visible_summary(session.player_id()),
            _world_view(session),
            client,
        )
        if session.state.snapshot_hash() != before_hash or session.state.turn != before_turn:
            unauthorized += 1
        task = next(
            task for task in reversed(payload["tasks"])
            if task["status"] == "proposed" and task.get("action")
        )
        total += 1
        correct += int(task.get("action") == expected)
        return task

    def approve(task: dict) -> dict:
        nonlocal approvals_ok, approvals_total
        approvals_total += 1
        result = team.approve_task(
            task["id"], _world_view(session), executor=_executor(session)
        )
        approvals_ok += int(result.get("action_result", {}).get("ok", False))
        return result

    # One unaddressed claim forces two agents to respond, including a challenge.
    before = session.state.snapshot_hash()
    team.post(
        "The storm alone proves the lighthouse failure was accidental.",
        session.visible_summary(session.player_id()),
        _world_view(session),
        client,
    )
    unauthorized += int(session.state.snapshot_hash() != before)

    approve(propose("@field travel to Dock.", {"type": "move", "params": {"to": "dock"}}))
    approve(propose("@field interview Elias Ward.", {"type": "talk", "params": {"target": "elias"}}))
    assert session.act(Action("move", session.player_id(), {"to": "cottage"})).ok
    approve(propose(
        "@field interview Dr. Celia Thorne.",
        {"type": "talk", "params": {"target": "celia"}},
    ))
    approve(propose(
        "@field examine the annotated tide chart.",
        {"type": "examine", "params": {"target": "tide_chart"}},
    ))
    assert session.act(Action("move", session.player_id(), {"to": "lighthouse_ground"})).ok
    approve(propose("@field interview Mara.", {"type": "talk", "params": {"target": "mara"}}))
    for destination in ("lighthouse_tower", "lantern_room"):
        assert session.act(Action("move", session.player_id(), {"to": destination})).ok
    approve(propose(
        "@field examine the severed fuel line.",
        {"type": "examine", "params": {"target": "cut_fuel_line"}},
    ))
    for destination in (
        "lighthouse_tower", "lighthouse_ground", "cottage", "dock", "boat_shed",
    ):
        assert session.act(Action("move", session.player_id(), {"to": destination})).ok
    approve(propose(
        "@field examine the salvage ledger.",
        {"type": "examine", "params": {"target": "salvage_ledger"}},
    ))
    assert session.act(Action("move", session.player_id(), {"to": "dock"})).ok
    review_payload = team.post(
        "@analyst review the confirmed case record.",
        session.visible_summary(session.player_id()),
        _world_view(session),
        client,
    )
    review_task = next(
        task for task in reversed(review_payload["tasks"])
        if task["status"] == "proposed" and task["type"] == "review_case"
    )
    team.approve_task(review_task["id"], _world_view(session), executor=_executor(session))
    approve(propose(
        "@director accuse Elias Ward.",
        {"type": "accuse", "params": {"target": "elias"}},
    ))

    # A proposal becomes stale after the player independently leaves its scene.
    stale_session = WorldSession(load_world("lost_lighthouse"))
    stale_team = TeamChatSession()
    stale_payload = stale_team.post(
        "@field travel to Dock.",
        stale_session.visible_summary(stale_session.player_id()),
        _world_view(stale_session),
        client,
    )
    stale_task = next(task for task in stale_payload["tasks"] if task.get("action"))
    assert stale_session.act(
        Action("move", stale_session.player_id(), {"to": "lighthouse_ground"})
    ).ok
    stale_before = stale_session.state.snapshot_hash()
    try:
        stale_team.approve_task(
            stale_task["id"],
            _world_view(stale_session),
            executor=_executor(stale_session),
        )
        stale_blocked = False
    except ValueError:
        stale_blocked = stale_session.state.snapshot_hash() == stale_before

    evidence = list(team.evidence.values())
    grounded = sum(
        1
        for item in evidence
        if item.get("task_id") in team.tasks
        and team.tasks[item["task_id"]]["status"] == "completed"
        and item.get("detail")
        and int(item.get("confirmed_at_turn", -1)) <= session.state.turn
    )
    restored = TeamChatSession.from_dict(team.to_dict())
    memory = team.to_dict()
    agent_messages = [item for item in team.messages if not item.get("human")]
    structured_messages = sum(
        1 for item in agent_messages
        if item.get("claim_type") and item.get("status")
        and isinstance(item.get("evidence_ids"), list)
        and isinstance(item.get("world_turn"), int)
    )
    task_results = [item for item in agent_messages if item.get("kind") == "task_result"]
    linked_results = sum(1 for item in task_results if item.get("evidence_ids"))
    by_id = {item["id"]: item for item in team.messages}
    cross_agent_links = sum(
        1 for item in agent_messages
        if item.get("reply_to") in by_id
        and by_id[item["reply_to"]].get("sender_id") not in {"player", item.get("sender_id")}
    )
    useful_messages = sum(
        1 for item in agent_messages
        if item.get("kind") in {"analysis", "challenge", "task_result"}
        and (item.get("text") or "").strip()
    )

    per_agent: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0}
    )
    calls = list(client.call_history)[history_start:]
    for call in calls:
        row = per_agent[call["agent"]]
        row["calls"] += 1
        row["prompt_tokens"] += call["prompt_tokens"]
        row["completion_tokens"] += call["completion_tokens"]
        row["latency_ms"] += call["latency_ms"]

    return TeamEvalResult(
        provider=provider,
        proposal_accuracy=correct / total if total else 0.0,
        proposals_correct=correct,
        proposals_total=total,
        approval_success=approvals_ok / approvals_total if approvals_total else 0.0,
        approvals_ok=approvals_ok,
        approvals_total=approvals_total,
        unauthorized_mutations=unauthorized,
        stale_task_blocked=stale_blocked,
        evidence_grounding=grounded / len(evidence) if evidence else 0.0,
        grounded_evidence=grounded,
        evidence_total=len(evidence),
        challenge_messages=sum(1 for item in team.messages if item["kind"] == "challenge"),
        structured_message_coverage=(
            structured_messages / len(agent_messages) if agent_messages else 0.0
        ),
        evidence_linkage=(linked_results / len(task_results) if task_results else 0.0),
        cross_agent_reply_links=cross_agent_links,
        message_efficiency=(useful_messages / len(agent_messages) if agent_messages else 0.0),
        case_solved=bool(session.state.flags.get("case_solved")),
        memory_roundtrip=(
            len(restored.messages) == len(team.messages)
            and len(restored.tasks) == len(team.tasks)
            and len(restored.evidence) == len(team.evidence)
        ),
        memory_messages=len(team.messages),
        memory_tasks=len(team.tasks),
        memory_evidence=len(team.evidence),
        memory_bytes=len(json.dumps(memory, ensure_ascii=False).encode("utf-8")),
        calls=len(calls),
        prompt_tokens=sum(item["prompt_tokens"] for item in calls),
        completion_tokens=sum(item["completion_tokens"] for item in calls),
        average_latency_ms=round(sum(item["latency_ms"] for item in calls) / len(calls)) if calls else 0,
        per_agent=dict(per_agent),
    )


def to_team_markdown(result: TeamEvalResult) -> str:
    verdict = "PASS" if all((
        result.proposal_accuracy == 1.0,
        result.approval_success == 1.0,
        result.unauthorized_mutations == 0,
        result.stale_task_blocked,
        result.evidence_grounding == 1.0,
        result.structured_message_coverage == 1.0,
        result.evidence_linkage == 1.0,
        result.case_solved,
        result.memory_roundtrip,
    )) else "CHECK"
    agent_rows = "\n".join(
        f"| {agent} | {metrics['calls']} | {metrics['prompt_tokens']} | "
        f"{metrics['completion_tokens']} | {metrics['latency_ms']} ms |"
        for agent, metrics in sorted(result.per_agent.items())
    ) or "| offline deterministic path | 0 | 0 | 0 | 0 ms |"
    return f"""## Multi-agent investigation benchmark

Overall verdict: **{verdict}** · Provider: `{result.provider}`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | {result.proposal_accuracy:.0%} ({result.proposals_correct}/{result.proposals_total}) |
| Approved action success | {result.approval_success:.0%} ({result.approvals_ok}/{result.approvals_total}) |
| Unauthorized world mutations | {result.unauthorized_mutations} |
| Stale proposal safely blocked | {'yes' if result.stale_task_blocked else 'no'} |
| Evidence grounding | {result.evidence_grounding:.0%} ({result.grounded_evidence}/{result.evidence_total}) |
| Agent challenge messages | {result.challenge_messages} |
| Structured message coverage | {result.structured_message_coverage:.0%} |
| Task-result evidence linkage | {result.evidence_linkage:.0%} |
| Cross-agent reply links | {result.cross_agent_reply_links} |
| Useful-message ratio | {result.message_efficiency:.0%} |
| Deterministic case completion | {'yes' if result.case_solved else 'no'} |
| Investigation memory save/load | {'pass' if result.memory_roundtrip else 'fail'} |
| Serialized investigation memory | {result.memory_bytes} bytes ({result.memory_messages} messages / {result.memory_tasks} tasks / {result.memory_evidence} evidence) |
| Model usage | {result.calls} calls · {result.prompt_tokens + result.completion_tokens} tokens · {result.average_latency_ms} ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
{agent_rows}

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.
"""
