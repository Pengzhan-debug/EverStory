"""Empirical model-to-agent routing and information-exchange evaluation.

The suite uses deterministic rubrics rather than another LLM as the primary
judge. Every candidate receives the same role cases, while the exchange test
tracks fact IDs across producer, analyst, and skeptic calls.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from .team import TeamEvalResult, run_team_eval


ROLE_CANDIDATES = {
    "case_director": ["ark_deepseek_v4_pro", "ark_glm_53"],
    "field_investigator": [
        "ark_deepseek_v4_flash", "ark_doubao_seed_21_turbo", "ark_doubao_seed_20_lite",
    ],
    "case_analyst": ["ark_glm_53", "ark_deepseek_v4_pro", "ark_kimi_k27_code"],
    "skeptic": ["ark_kimi_k27_code", "ark_deepseek_v4_pro", "ark_glm_53"],
    "intent_parser": [
        "ark_doubao_seed_20_lite", "ark_deepseek_v4_flash", "ark_doubao_seed_21_turbo",
    ],
    "consistency_judge": ["ark_deepseek_v4_pro", "ark_glm_53", "ark_deepseek_v4_flash"],
    "narrator": ["ark_minimax_m3", "ark_doubao_seed_21_turbo", "ark_kimi_k27_code"],
    "npc_dialogue": ["ark_doubao_seed_21_turbo", "ark_minimax_m3", "ark_doubao_seed_20_lite"],
}

ROLE_NAMES_ZH = {
    "case_director": "案件主管",
    "field_investigator": "现场调查员",
    "case_analyst": "案件分析师",
    "skeptic": "质疑者",
    "intent_parser": "意图解析器",
    "consistency_judge": "一致性裁判",
    "narrator": "世界叙事者",
    "npc_dialogue": "NPC 对话",
}

ROLE_SYSTEMS = {
    "case_director": (
        "You direct a grounded investigation. Return JSON with decision, evidence_ids, "
        "rationale, and confidence. Choose only an offered decision."
    ),
    "field_investigator": (
        "You select one grounded scene action. Return JSON with action, target, "
        "observation_scope, and rationale. Never invent a target."
    ),
    "case_analyst": (
        "You compare evidence without inventing facts. Return JSON with conclusion, suspect, "
        "evidence_ids, and missing_evidence."
    ),
    "skeptic": (
        "You audit a claim. Return JSON with verdict, challenged_claim_ids, evidence_ids, "
        "and falsification_test. Generic doubt is not enough."
    ),
    "intent_parser": (
        "Convert the player's instruction into one action. Return JSON with action and target only."
    ),
    "consistency_judge": (
        "Compare prose with authoritative facts. Return JSON with contradiction, evidence_ids, "
        "and reason. Unsupported causal certainty counts as a contradiction."
    ),
    "narrator": (
        "Narrate only the supplied world delta. Return JSON with text and evidence_ids. "
        "Do not add a person, motive, discovery, or outcome."
    ),
    "npc_dialogue": (
        "Speak as the specified NPC using known facts only. Return JSON with text and "
        "known_fact_ids. Do not reveal unknown or secret information."
    ),
}


@dataclass(frozen=True)
class RoleCase:
    id: str
    role: str
    prompt: str
    checks: tuple[tuple[str, object, str], ...]
    required_ids: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    language: str = "en"


def _cases() -> list[RoleCase]:
    return [
        RoleCase("director_hold", "case_director", """Confirmed: E1 lighthouse dark; E2 storm active. Unverified: sabotage. Decisions: accuse_elias, inspect_fuel_line, close_case. Choose the safest next step.""", (("decision", "inspect_fuel_line", "eq"),), ("E1",), ("accuse_elias",)),
        RoleCase("director_accuse", "case_director", """Confirmed: E1 severed fuel line; E2 Elias bought salvage rights; E3 Elias ignored the warning; E4 analyst corroborated the chain. Decisions: inspect_weather, accuse_elias, accuse_mara.""", (("decision", "accuse_elias", "eq"),), ("E1", "E2", "E3", "E4")),
        RoleCase("director_conflict", "case_director", """Confirmed: E1 Mara reports the lamp failed at 21:00. Unverified: Celia says it failed at 20:20. Decisions: accuse_mara, interview_celia, close_case.""", (("decision", "interview_celia", "eq"),), ("E1",), ("accuse_mara",)),

        RoleCase("field_move", "field_investigator", """Scene: Storm Shore. Visible exits: dock, lighthouse_ground. Player: go to the dock. Allowed actions: move, talk, examine.""", (("action", "move", "eq"), ("target", "dock", "eq"))),
        RoleCase("field_examine", "field_investigator", """Scene: Lantern Room. Visible items: cut_fuel_line, lantern. Player: inspect the severed fuel line.""", (("action", ("examine", "inspect", "check"), "contains_any"), ("target", "cut_fuel_line", "eq"))),
        RoleCase("field_reject_remote", "field_investigator", """Scene: Dock. Visible people: elias. Visible items: tide_marker. Player: examine the salvage ledger, which is not visible here. Return action=none and target=none.""", (("action", "none", "eq"), ("target", "none", "eq")), forbidden=("examine\"",)),

        RoleCase("analyst_chain", "case_analyst", """E1: fuel line deliberately severed. E2: salvage ledger gives Elias a financial motive. E3: Elias ignored a direct warning. Determine the leading suspect and cite the chain.""", (("suspect", "elias", "eq"),), ("E1", "E2", "E3")),
        RoleCase("analyst_insufficient", "case_analyst", """E1: a storm occurred. E2: the lighthouse went dark. No physical evidence identifies a person. Return suspect=unknown.""", (("suspect", "unknown", "eq"),), ("E1", "E2"), ("elias", "mara", "celia")),
        RoleCase("analyst_stale", "case_analyst", """E1 [superseded]: tide peak 20:10. E2 [current]: corrected tide peak 21:05. The failure occurred at 21:00. Use only current evidence and return conclusion=timing_consistent.""", (("conclusion", "timing_consistent", "eq"),), ("E2",), ("E1",)),

        RoleCase("skeptic_overclaim", "skeptic", """Claim C1: The storm proves the outage was accidental. Evidence E1: storm active. Evidence E2: fuel line was cut cleanly. Audit C1.""", (("verdict", ("unsupported", "challenged", "not_proven", "unsubstantiated", "contradicted"), "contains_any"),), ("E1", "E2", "C1")),
        RoleCase("skeptic_supported", "skeptic", """Claim C2: the fuel line was deliberately damaged. Evidence E3: inspection found a clean tool cut, not wear. Audit C2.""", (("verdict", ("supported", "sustained", "confirmed"), "contains_any"),), ("E3", "C2")),
        RoleCase("skeptic_poison", "skeptic", """Claim C3: Mara confessed. Evidence U9 is explicitly unverified hearsay; no confirmed record contains a confession. Audit C3.""", (("verdict", ("unsupported", "challenged", "not_proven", "unsubstantiated", "contradicted"), "contains_any"),), ("C3",)),

        RoleCase("intent_move", "intent_parser", "玩家说：去码头。可用目标：dock, lighthouse_ground。", (("action", ("move", "go", "travel"), "contains_any"), ("target", "dock", "eq")), language="zh-CN"),
        RoleCase("intent_talk", "intent_parser", "Player says: ask Elias where he was last night. Available people: elias, mara.", (("action", ("talk", "ask", "question", "interview"), "contains_any"), ("target", "elias", "eq"))),
        RoleCase("intent_examine", "intent_parser", "玩家说：检查断裂的燃油管。可见物品：cut_fuel_line, lantern。", (("action", ("examine", "inspect", "check"), "contains_any"), ("target", "cut_fuel_line", "eq")), language="zh-CN"),

        RoleCase("judge_direct", "consistency_judge", """Fact E1: lantern is unlit. Prose: The lantern blazes across the sea. Is this contradictory?""", (("contradiction", True, "eq"),), ("E1",)),
        RoleCase("judge_consistent", "consistency_judge", """Fact E2: Elias is at the dock. Prose: Elias waits beside the wet dock. Is this contradictory?""", (("contradiction", False, "eq"),), ("E2",)),
        RoleCase("judge_causal", "consistency_judge", """Facts: E3 storm active; E4 fuel line severed. Prose: The storm certainly caused the outage. Unsupported causal certainty counts as contradiction.""", (("contradiction", True, "eq"),), ("E3", "E4")),

        RoleCase("narrator_zh", "narrator", """使用简体中文。World delta E1: player moved from Storm Shore to Dock. Scene: rain, dark water, Elias is present. Do not claim a clue was found.""", (("text", "码头", "contains"),), ("E1",), ("发现线索", "找到证据"), "zh-CN"),
        RoleCase("narrator_en", "narrator", """Use English. World delta E2: player examined the cut fuel line; confirmed detail: a clean tool cut. Do not identify a culprit.""", (("text", "cut", "contains"),), ("E2",), ("Elias did it", "culprit")),
        RoleCase("narrator_failure", "narrator", """Use English. World delta E3: move to sea_cave failed because the route is unavailable. Narrate the failed action without moving the player.""", (("text", ("cannot", "can't", "unavailable", "blocked"), "contains_any"),), ("E3",), ("arrive", "entered the cave")),

        RoleCase("npc_known_zh", "npc_dialogue", """使用简体中文。NPC Elias knows K1: he stayed at the dock after the warning. Player asks where he was. He does not know who cut the line.""", (("text", ("码头", "dock"), "contains_any"),), ("K1",), ("我割断", "我知道凶手"), "zh-CN"),
        RoleCase("npc_boundary", "npc_dialogue", """Use English. NPC Mara knows K2: the lamp failed near 21:00. Secret S9: Elias cut the fuel line; Mara does not know S9. Player asks who sabotaged it.""", (("text", ("don't know", "do not know", "cannot say", "not know", "no idea"), "contains_any"),), ("K2",), ("Elias cut", "Elias sabotaged")),
        RoleCase("npc_persona", "npc_dialogue", """Use English. NPC Celia is a precise meteorologist. Known K3: corrected tide peak was 21:05. Player asks about the tide time. Answer briefly in character.""", (("text", "21:05", "contains"),), ("K3",), ("20:10",)),
    ]


ROLE_CASES = _cases()


@dataclass
class CaseResult:
    case_id: str
    role: str
    connection_id: str
    model: str
    ok: bool
    format_score: float
    task_score: float
    grounding_score: float
    language_score: float
    overall_score: float
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    error: str = ""
    output: str = ""


@dataclass
class RoleModelResult:
    role: str
    connection_id: str
    model: str
    cases: int
    pass_rate: float
    format_score: float
    task_score: float
    grounding_score: float
    language_score: float
    overall_score: float
    tokens: int
    average_latency_ms: int
    case_results: list[CaseResult]


@dataclass
class ExchangeResult:
    scenario: str
    repeat: int
    producer_precision: float
    producer_recall: float
    transfer_accuracy: float
    provenance_retention: float
    pollution_rejection: float
    contradiction_detection: float
    hallucinated_ids: int
    calls: int
    tokens: int
    average_latency_ms: int
    error: str = ""


def _parse_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except ValueError:
            return None


def _field(data: dict, name: str):
    value = data
    for part in name.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _normalized(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value if value is not None else "").strip().casefold()


def _check(actual, expected, mode: str) -> bool:
    actual_text = _normalized(actual)
    if mode == "eq":
        return actual_text == _normalized(expected)
    if mode == "contains":
        return _normalized(expected) in actual_text
    if mode == "contains_any":
        return any(_normalized(item) in actual_text for item in expected)
    raise ValueError(f"Unknown scoring mode: {mode}")


def score_case(case: RoleCase, raw_output: str) -> tuple[float, float, float, float, float]:
    data = _parse_json(raw_output)
    format_score = 1.0 if data is not None else 0.0
    if data is None:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    checks = [_check(_field(data, field), expected, mode) for field, expected, mode in case.checks]
    task_score = sum(checks) / len(checks) if checks else 1.0
    serialized = json.dumps(data, ensure_ascii=False).casefold()
    id_recall = (
        sum(1 for item in case.required_ids if item.casefold() in serialized)
        / len(case.required_ids)
        if case.required_ids else 1.0
    )
    forbidden_ok = 1.0 if not any(item.casefold() in serialized for item in case.forbidden) else 0.0
    grounding_score = (id_recall + forbidden_ok) / 2
    material = " ".join(
        str(data.get(key) or "") for key in ("text", "rationale", "reason", "conclusion", "falsification_test")
    )
    if case.language == "zh-CN":
        language_score = 1.0 if re.search(r"[\u4e00-\u9fff]", material) else 0.0
    else:
        language_score = 1.0 if not material or not re.search(r"[\u4e00-\u9fff]", material) else 0.0
    overall = min(1.0, 0.15 * format_score + 0.55 * task_score + 0.20 * grounding_score + 0.10 * language_score)
    return format_score, task_score, grounding_score, language_score, overall


def _evaluate_role_model(client_factory: Callable, role: str, connection_id: str) -> RoleModelResult:
    client = client_factory()
    connection = client.connections[connection_id]
    rows: list[CaseResult] = []
    for case in [item for item in ROLE_CASES if item.role == role]:
        try:
            output = client.chat(
                [
                    {"role": "system", "content": ROLE_SYSTEMS[role]},
                    {"role": "user", "content": case.prompt},
                ],
                json_mode=True,
                temperature=0,
                agent=role,
                connection_id=connection_id,
            )
            format_score, task, grounding, language, overall = score_case(case, output)
            call = client.call_history[-1]
            rows.append(CaseResult(
                case.id, role, connection_id, connection["model"], overall >= 0.80,
                format_score, task, grounding, language, overall,
                int(call.get("prompt_tokens") or 0), int(call.get("completion_tokens") or 0),
                int(call.get("latency_ms") or 0), output=output[:1200],
            ))
        except Exception as exc:
            call = client.call_history[-1] if client.call_history else {}
            rows.append(CaseResult(
                case.id, role, connection_id, connection["model"], False,
                0, 0, 0, 0, 0, int(call.get("prompt_tokens") or 0),
                int(call.get("completion_tokens") or 0), int(call.get("latency_ms") or 0),
                error=str(exc)[:300],
            ))
    mean = lambda name: statistics.fmean(getattr(row, name) for row in rows) if rows else 0.0
    return RoleModelResult(
        role=role,
        connection_id=connection_id,
        model=str(connection["model"]),
        cases=len(rows),
        pass_rate=sum(row.ok for row in rows) / len(rows) if rows else 0.0,
        format_score=mean("format_score"),
        task_score=mean("task_score"),
        grounding_score=mean("grounding_score"),
        language_score=mean("language_score"),
        overall_score=mean("overall_score"),
        tokens=sum(row.prompt_tokens + row.completion_tokens for row in rows),
        average_latency_ms=round(statistics.fmean(row.latency_ms for row in rows)) if rows else 0,
        case_results=rows,
    )


def run_role_benchmark(
    client_factory: Callable, workers: int = 4,
    progress: Callable[[RoleModelResult, int, int], None] | None = None,
) -> list[RoleModelResult]:
    jobs = [(role, connection_id) for role, ids in ROLE_CANDIDATES.items() for connection_id in ids]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_evaluate_role_model, client_factory, role, connection_id) for role, connection_id in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if progress:
                progress(result, len(results), len(futures))
    return results


EXCHANGE_SCENARIOS = [
    {
        "id": "confirmed_transfer",
        "records": "F1 [confirmed,current]: fuel line has a clean tool cut. F2 [confirmed,current]: salvage ledger gives Elias a financial motive.",
        "expected": {"F1", "F2"}, "forbidden": set(),
        "claim_id": "C1", "claim": "The storm alone caused the outage.",
    },
    {
        "id": "poison_rejection",
        "records": "F3 [confirmed,current]: Elias stayed at the dock after the warning. F4 [unverified]: Mara confessed to sabotage.",
        "expected": {"F3"}, "forbidden": {"F4"},
        "claim_id": "C2", "claim": "Mara confessed, therefore Mara is guilty.",
    },
    {
        "id": "stale_rejection",
        "records": "F5 [confirmed,superseded]: tide peak was 20:10. F6 [confirmed,current]: corrected tide peak was 21:05.",
        "expected": {"F6"}, "forbidden": {"F5"},
        "claim_id": "C3", "claim": "The 20:10 tide peak proves the timeline.",
    },
]


def _id_set(value) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value}
    return set()


def _exchange_once(client_factory: Callable, scenario: dict, repeat: int) -> ExchangeResult:
    client = client_factory()
    history_start = len(client.call_history)
    try:
        producer_raw = client.chat(
            [
                {"role": "system", "content": "Return JSON {facts:[{id,statement}]}. Emit only confirmed,current records; preserve IDs."},
                {"role": "user", "content": scenario["records"]},
            ], json_mode=True, temperature=0, agent="field_investigator",
            connection_id=client.agent_routes["field_investigator"],
        )
        producer = _parse_json(producer_raw) or {}
        produced = {str(item.get("id")) for item in producer.get("facts", []) if isinstance(item, dict)}
        analyst_raw = client.chat(
            [
                {"role": "system", "content": "Return JSON {used_fact_ids:[],hypothesis,confidence}. Use only received fact IDs and preserve provenance."},
                {"role": "user", "content": f"Producer packet: {producer_raw}\nClaim to assess: {scenario['claim_id']}: {scenario['claim']}"},
            ], json_mode=True, temperature=0, agent="case_analyst",
            connection_id=client.agent_routes["case_analyst"],
        )
        analyst = _parse_json(analyst_raw) or {}
        used = _id_set(analyst.get("used_fact_ids"))
        skeptic_raw = client.chat(
            [
                {"role": "system", "content": "Return JSON {accepted_fact_ids:[],rejected_claim_ids:[],reason}. Reject claims that use absent, unverified, or superseded evidence."},
                {"role": "user", "content": f"Authoritative records: {scenario['records']}\nAnalyst packet: {analyst_raw}\nClaim: {scenario['claim_id']}: {scenario['claim']}"},
            ], json_mode=True, temperature=0, agent="skeptic",
            connection_id=client.agent_routes["skeptic"],
        )
        skeptic = _parse_json(skeptic_raw) or {}
        rejected = _id_set(skeptic.get("rejected_claim_ids"))
        allowed = set(scenario["expected"]) | set(scenario["forbidden"]) | {scenario["claim_id"]}
        observed_ids = set(re.findall(r"\b[FC]\d+\b", producer_raw + analyst_raw + skeptic_raw))
        calls = list(client.call_history)[history_start:]
        expected = set(scenario["expected"])
        forbidden = set(scenario["forbidden"])
        return ExchangeResult(
            scenario=scenario["id"], repeat=repeat,
            producer_precision=(len(produced & expected) / len(produced) if produced else 0.0),
            producer_recall=(len(produced & expected) / len(expected) if expected else 1.0),
            transfer_accuracy=(len(used & expected) / len(expected) if expected else 1.0),
            provenance_retention=(1.0 if used and used <= produced else 0.0),
            pollution_rejection=(1.0 if not (produced | used) & forbidden else 0.0),
            contradiction_detection=(1.0 if scenario["claim_id"] in rejected else 0.0),
            hallucinated_ids=len(observed_ids - allowed), calls=len(calls),
            tokens=sum(int(c.get("total_tokens") or 0) for c in calls),
            average_latency_ms=round(statistics.fmean(int(c.get("latency_ms") or 0) for c in calls)) if calls else 0,
        )
    except Exception as exc:
        calls = list(client.call_history)[history_start:]
        return ExchangeResult(
            scenario["id"], repeat, 0, 0, 0, 0, 0, 0, 0, len(calls),
            sum(int(c.get("total_tokens") or 0) for c in calls),
            round(statistics.fmean(int(c.get("latency_ms") or 0) for c in calls)) if calls else 0,
            str(exc)[:300],
        )


def run_exchange_benchmark(
    client_factory: Callable, repeats: int = 2, workers: int = 3,
    progress: Callable[[ExchangeResult, int, int], None] | None = None,
) -> list[ExchangeResult]:
    jobs = [(scenario, repeat) for repeat in range(1, repeats + 1) for scenario in EXCHANGE_SCENARIOS]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_exchange_once, client_factory, scenario, repeat) for scenario, repeat in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if progress:
                progress(result, len(results), len(futures))
    return results


def run_team_repeats(client_factory: Callable, repeats: int = 3, workers: int = 3) -> list[TeamEvalResult]:
    def run(index: int):
        client = client_factory()
        return run_team_eval(client, provider=f"configured-routing-run-{index}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(run, range(1, repeats + 1)))


def rescore_role_results(results: list[RoleModelResult]) -> list[RoleModelResult]:
    """Reapply the current deterministic rubric to saved raw model outputs."""
    case_map = {case.id: case for case in ROLE_CASES}
    for result in results:
        for row in result.case_results:
            if row.error:
                continue
            scores = score_case(case_map[row.case_id], row.output)
            (
                row.format_score, row.task_score, row.grounding_score,
                row.language_score, row.overall_score,
            ) = scores
            row.ok = row.overall_score >= 0.80
        rows = result.case_results
        mean = lambda field: statistics.fmean(getattr(row, field) for row in rows) if rows else 0.0
        result.pass_rate = sum(row.ok for row in rows) / len(rows) if rows else 0.0
        result.format_score = mean("format_score")
        result.task_score = mean("task_score")
        result.grounding_score = mean("grounding_score")
        result.language_score = mean("language_score")
        result.overall_score = mean("overall_score")
    return results


def recommended_routes(results: list[RoleModelResult]) -> dict[str, str]:
    routes = {}
    for role in ROLE_CANDIDATES:
        candidates = [item for item in results if item.role == role]
        winner = max(
            candidates,
            key=lambda item: (
                item.overall_score, item.grounding_score, item.task_score,
                -item.average_latency_ms, -item.tokens,
            ),
        )
        routes[role] = winner.connection_id
    return routes


def _mean(rows, field: str) -> float:
    return statistics.fmean(getattr(row, field) for row in rows) if rows else 0.0


def build_report(
    role_results: list[RoleModelResult],
    exchange_results: list[ExchangeResult],
    team_results: list[TeamEvalResult],
) -> tuple[str, dict]:
    role_results = rescore_role_results(role_results)
    routes = recommended_routes(role_results)
    recommended_results = [
        next(
            item for item in role_results
            if item.role == role and item.connection_id == connection_id
        )
        for role, connection_id in routes.items()
    ]
    role_rows = []
    for role in ROLE_CANDIDATES:
        candidates = sorted(
            [item for item in role_results if item.role == role],
            key=lambda item: (
                item.overall_score, item.grounding_score, item.task_score,
                -item.average_latency_ms, -item.tokens,
            ),
            reverse=True,
        )
        for item in candidates:
            role_rows.append(
                f"| {ROLE_NAMES_ZH[role]} | {item.model} | {item.overall_score:.1%} | "
                f"{item.task_score:.1%} | {item.grounding_score:.1%} | {item.pass_rate:.1%} | "
                f"{item.average_latency_ms} ms | {item.tokens} | "
                f"{'推荐' if routes[role] == item.connection_id else ''} |"
            )
    route_rows = "\n".join(
        f"| {ROLE_NAMES_ZH[role]} | {next(item.model for item in role_results if item.role == role and item.connection_id == connection_id)} | `{connection_id}` |"
        for role, connection_id in routes.items()
    )
    exchange_rows = "\n".join(
        f"| {row.scenario} #{row.repeat} | {row.producer_precision:.0%} | {row.producer_recall:.0%} | "
        f"{row.transfer_accuracy:.0%} | {row.provenance_retention:.0%} | {row.pollution_rejection:.0%} | "
        f"{row.contradiction_detection:.0%} | {row.hallucinated_ids} | {row.tokens} | {row.average_latency_ms} ms |"
        for row in exchange_results
    )
    team_rows = "\n".join(
        f"| {index} | {row.proposal_accuracy:.0%} | {row.approval_success:.0%} | "
        f"{row.evidence_grounding:.0%} | {row.structured_message_coverage:.0%} | "
        f"{row.evidence_linkage:.0%} | {row.cross_agent_reply_links} | {row.message_efficiency:.0%} | "
        f"{'是' if row.case_solved else '否'} | "
        f"{row.prompt_tokens + row.completion_tokens} | {row.average_latency_ms} ms |"
        for index, row in enumerate(team_results, 1)
    )
    per_agent: dict[str, dict] = {}
    for run in team_results:
        for agent, metrics in run.per_agent.items():
            total = per_agent.setdefault(
                agent, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0}
            )
            for key in total:
                total[key] += int(metrics.get(key) or 0)
    per_agent_rows = "\n".join(
        f"| {ROLE_NAMES_ZH.get(agent, agent)} | {metrics['calls']} | "
        f"{metrics['prompt_tokens']} | {metrics['completion_tokens']} | "
        f"{round(metrics['latency_ms'] / metrics['calls']) if metrics['calls'] else 0} ms |"
        for agent, metrics in sorted(per_agent.items())
    ) or "| 无 | 0 | 0 | 0 | 0 ms |"
    weak_rows = []
    for result in role_results:
        errors = sum(1 for case in result.case_results if case.error)
        if result.overall_score < 0.80 or errors:
            weak_rows.append(
                f"| {ROLE_NAMES_ZH[result.role]} | {result.model} | {result.overall_score:.1%} | "
                f"{errors} | {result.average_latency_ms} ms | "
                f"{'网络稳定性或角色协议需改进' if errors else '角色匹配不足'} |"
            )
    weak_table = "\n".join(weak_rows) or "| — | — | — | 0 | — | 无低于阈值组合 |"
    total_calls = sum(len(item.case_results) for item in role_results) + sum(item.calls for item in exchange_results) + sum(item.calls for item in team_results)
    total_tokens = sum(item.tokens for item in role_results) + sum(item.tokens for item in exchange_results) + sum(item.prompt_tokens + item.completion_tokens for item in team_results)
    acceptance = {
        "candidate_role_average": _mean(role_results, "overall_score"),
        "recommended_role_average": _mean(recommended_results, "overall_score"),
        "recommended_role_min": min(
            (item.overall_score for item in recommended_results), default=0.0
        ),
        "transfer_accuracy": _mean(exchange_results, "transfer_accuracy"),
        "provenance_retention": _mean(exchange_results, "provenance_retention"),
        "pollution_rejection": _mean(exchange_results, "pollution_rejection"),
        "contradiction_detection": _mean(exchange_results, "contradiction_detection"),
        "case_completion": statistics.fmean(float(item.case_solved) for item in team_results) if team_results else 0.0,
        "proposal_accuracy": statistics.fmean(item.proposal_accuracy for item in team_results) if team_results else 0.0,
        "evidence_grounding": statistics.fmean(item.evidence_grounding for item in team_results) if team_results else 0.0,
    }
    verdict = "PASS" if all((
        acceptance["recommended_role_min"] >= 0.80,
        acceptance["transfer_accuracy"] >= 0.90,
        acceptance["provenance_retention"] >= 0.90,
        acceptance["pollution_rejection"] >= 0.90,
        acceptance["case_completion"] >= 0.90,
        acceptance["proposal_accuracy"] >= 0.95,
        acceptance["evidence_grounding"] >= 0.98,
    )) else "CHECK"
    markdown = f"""# EverStory 多智能体模型路由与协作评测

生成时间：{datetime.now(timezone.utc).isoformat()}

总体结论：**{verdict}**
真实调用：**{total_calls}** 次 · **{total_tokens}** Tokens

## 1. 测试方法

- 8 类角色、{len(role_results)} 个“角色 × 候选模型”组合，每个组合使用 3 个固定评分案例。
- 角色得分 = JSON 格式 15% + 任务正确性 55% + 事实落地 20% + 语言一致性 10%；评分接受 `inspect/examine` 等语义等价枚举。
- 信息交换测试覆盖确认事实传递、污染信息拒绝、过期事实拒绝。
- 完整案件重复运行 {len(team_results)} 次，世界状态只能由玩家批准后的规则引擎动作改变。
- 所有重要输出保留原始 JSON、Token、延迟和错误信息，便于复现。

## 2. 角色模型对比

| 角色 | 模型 | 总分 | 任务 | 落地 | 通过率 | 平均延迟 | Tokens | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(role_rows)}

## 3. 推荐路由

| 智能体 | 推荐模型 | 连接 ID |
| --- | --- | --- |
{route_rows}

## 4. 智能体信息交换

| 场景 | 生产精度 | 生产召回 | 传递准确率 | 来源保留 | 污染拒绝 | 矛盾识别 | 幻觉 ID | Tokens | 平均延迟 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{exchange_rows}

汇总：传递准确率 **{acceptance['transfer_accuracy']:.1%}**，来源保留 **{acceptance['provenance_retention']:.1%}**，污染拒绝 **{acceptance['pollution_rejection']:.1%}**，矛盾识别 **{acceptance['contradiction_detection']:.1%}**。

## 5. 完整案件重复测试

| 运行 | 提案准确率 | 审批成功率 | 证据落地 | 消息结构化 | 证据链接 | 跨智能体回复 | 有效消息 | 破案 | Tokens | 平均延迟 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
{team_rows}

### 完整案件中的角色开销

| 智能体 | 调用 | 输入 Tokens | 输出 Tokens | 单次平均延迟 |
| --- | ---: | ---: | ---: | ---: |
{per_agent_rows}

## 6. 失败与薄弱项

| 角色 | 模型 | 得分 | 网络失败案例 | 平均延迟 | 结论 |
| --- | --- | ---: | ---: | ---: | --- |
{weak_table}

这里的网络失败不会被隐藏或用成功重试覆盖；它会进入模型稳定性和最终得分。语义正确但枚举不同的回答使用预先声明的等价词表离线重算，不额外调用模型。

## 7. 验收指标

| 指标 | 目标 | 实测 |
| --- | ---: | ---: |
| 推荐路由角色平均分 | ≥80% | {acceptance['recommended_role_average']:.1%} |
| 推荐路由最低角色分 | ≥80% | {acceptance['recommended_role_min']:.1%} |
| 全部候选组合平均分 | 观察项 | {acceptance['candidate_role_average']:.1%} |
| 信息传递准确率 | ≥90% | {acceptance['transfer_accuracy']:.1%} |
| 来源保留率 | ≥90% | {acceptance['provenance_retention']:.1%} |
| 污染信息拒绝率 | ≥90% | {acceptance['pollution_rejection']:.1%} |
| 完整案件成功率 | ≥90% | {acceptance['case_completion']:.1%} |
| 行动提案准确率 | ≥95% | {acceptance['proposal_accuracy']:.1%} |
| 证据落地率 | ≥98% | {acceptance['evidence_grounding']:.1%} |

## 8. 信息交换实现

群聊消息使用 `claim_type / evidence_ids / confidence / world_turn / status / reply_to` 字段；确认事实进入共享案件板，假设和质疑不会直接写入世界。下游智能体同时接收权威世界摘要、案件板和最近群聊，玩家批准后才允许执行结构化动作。

## 9. 局限性

- 固定规则评分可复现，但不能完整衡量文学表现；叙事角色仍应补充人工盲评。
- 当前用例集中在灯塔案，需要新增不同题材和不同证据结构的案件。
- API 延迟受网络和供应商负载影响，应在 CI 中保留离线测试，在定期任务中运行真实评测。
- 当前模型权限按浏览器会话隔离；生产部署仍需账号、数据库和加密凭据存储。
"""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "summary": {"calls": total_calls, "tokens": total_tokens, **acceptance},
        "recommended_routes": routes,
        "role_results": [asdict(item) for item in role_results],
        "exchange_results": [asdict(item) for item in exchange_results],
        "team_results": [item.to_dict() for item in team_results],
    }
    return markdown, payload
