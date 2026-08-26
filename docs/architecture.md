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
- **Production follow-up**: durable sessions (Postgres/Redis), authentication,
  rate limits, secret management, and multi-instance coordination.
