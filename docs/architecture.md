# EverStory Architecture

## 1. Problem

Long-horizon LLM interaction is unreliable: models forget, contradict
themselves, and invent state. Any serious agent/game/assistant product needs a
source of truth that the model cannot corrupt.

## 2. Design principle

> **The LLM proposes. The state machine decides.**

The world is a structured, versioned state graph. The LLM is only ever given:
the current state, a description of the world, and the ability to emit
structured action proposals. Every proposal passes through declarative
precondition checks before deterministic effects are applied.

## 3. Core loop

```text
user text / LLM intent
        |
        v
action proposal  (typed: move/take/give/use/open/talk/examine/accuse/wait)
        |
        v
precondition checks  (declarative rule DSL)
        |
        +-- rejected -> deterministic, human-readable reason (no hallucination)
        |
        v
effects applied  (location, ownership, attributes, flags, time)
        |
        v
event recorded + state snapshot (turn-versioned, rollback/branch capable)
        |
        v
narration generated from the *actual* state delta (grounded, optional judge)
```

## 4. Multi-agent investigation boundary

```text
Lead Investigator (human)
        |
        v
group discussion  <---->  Director / Field / Analyst / Skeptic
  (hypotheses only)           |      mutual challenges
        |                     v
        +------------ structured task proposal
                              |
                       player approval
                              |
                    scene + stale-task validation
                              |
                  deterministic WorldSession.act
                              |
          evidence record (source / task / location / turn)
                              |
       3 examinations + 3 testimonies + analyst corroboration
                              |
                  director accusation gate
```

The normal narration chat cannot execute `examine` or `accuse`; those two
authoritative operations must pass through the investigation task protocol.
The team chat itself never receives a world mutation handle.

Every team message carries `claim_type`, `evidence_ids`, `confidence`,
`world_turn`, `status`, and `reply_to`. Confirmed observations are rendered
from the authoritative evidence board; hypotheses and challenges remain
non-authoritative. Each responding agent receives the current world summary,
the shared case board, and a bounded recent transcript, making provenance
retention and cross-agent reply links directly measurable.

## 5. State model

- **Entity** — id, kind (character/item/location/quest/concept), name,
  description, attributes (JSON), location, owner.
- **Relationship** — typed edge: `knows`, `owns`, `enemy_of`, ...
- **Flags & time** — world-level mutable state.
- **Snapshot** — full state copy + content hash per turn; `rollback(turn)`
  rewinds; future work: branch/fork from any snapshot.

Entities and relationships are loaded from declarative TOML world files, so a
new world is data, not code.

## 6. Rule DSL

Actions are declared as rules with two parts:

- **Checks** (preconditions): `here`, `same_location`, `inventory`,
  `not_owned`, `connected`, `attribute`, `flag`.
- **Effects** (transitions): `set_location`, `set_owner`, `set_attribute`,
  `set_flag`, `advance_time`.

References use `$actor`, `$here`, and `$param.<name>`; entity names are
resolved by id, exact name, unique prefix, or unique substring. Composite
actions (`use`, `open`) dispatch to world-driven handlers keyed on entity
attributes (`unlock_key`, `contains`, `fill_with`, `light_with`), so new
interactions can be authored without engine changes.

## 7. Why this survives long horizons

- The LLM never holds state; it is given a *rendering* of it each turn.
- Rejected actions produce deterministic reasons ("The chest is locked."),
  which the narrator turns into prose — the model cannot argue with truth.
- Every turn is versioned, so contradictions are detectable and recoverable.
- Narration is grounded in state deltas, not model memory.

## 8. Implementation status

- **Implemented**: engine core, rule DSL, snapshots/rollback, LLM client
  (stub + OpenAI-compatible API), intent parser, grounded narrator,
  consistency judge, entity-card/summary memory, FastAPI/SSE web UI with live
  state inspector, main/team transcript persistence, a multi-agent evidence
  gate, a three-architecture evaluation harness, and symbolic
  world-model induction (rules learned from trajectories, with a held-out
  accuracy check and counterfactual predictions).

## 9. Model credential and usage boundary

```text
agent role -> immutable route snapshot -> exactly one connection
                                      |-> platform credential + session quota
                                      `-> player BYOK + separate accounting
```

- Platform connections are created from server environment variables and are
  read-only to the player settings API.
- New browser-configured connections are always classified as `personal`; a
  failed personal request retries only the same endpoint and never falls back
  to a platform credential.
- Every live call records timestamp, agent, connection, credential source,
  model, prompt/completion tokens, estimated cost, latency, result, and a
  bounded error summary. The browser receives no raw key.
- The current local build isolates worlds, settings, and usage with an
  anonymous HttpOnly session cookie and an in-memory runtime. Production scale
  requires authenticated, signed sessions; PostgreSQL for users/worlds/routes/
  usage; envelope-encrypted BYOK secrets; and Redis-backed quotas/rate limits.

## 10. Empirical routing and evaluation

`python -m scripts.run_full_agent_evaluation` evaluates 8 runtime/team roles
against 23 candidate assignments, then runs evidence-transfer, stale-fact,
poison-rejection, and repeated end-to-end case tests. Phase checkpoints make
the live benchmark resumable; `--refresh-team` reuses role/exchange results and
reruns only the final routed cases. Raw outputs, errors, latency, tokens, and
the generated report are stored under `reports/`.

The checked-in run selected DeepSeek V4 Pro (Director), Doubao Seed 2.0 Lite
(Field/Intent/NPC), GLM 5.3 (Analyst), Kimi K2.7 Code (Skeptic), DeepSeek V4
Flash (Judge), and MiniMax M3 (Narrator). See
[`reports/agent-routing-evaluation-zh.md`](../reports/agent-routing-evaluation-zh.md).
