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
action proposal  (typed: move/take/give/use/open/talk/wait)
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

## 4. State model

- **Entity** — id, kind (character/item/location/quest/concept), name,
  description, attributes (JSON), location, owner.
- **Relationship** — typed edge: `knows`, `owns`, `enemy_of`, ...
- **Flags & time** — world-level mutable state.
- **Snapshot** — full state copy + content hash per turn; `rollback(turn)`
  rewinds; future work: branch/fork from any snapshot.

Entities and relationships are loaded from declarative TOML world files, so a
new world is data, not code.

## 5. Rule DSL

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

## 6. Why this survives long horizons

- The LLM never holds state; it is given a *rendering* of it each turn.
- Rejected actions produce deterministic reasons ("The chest is locked."),
  which the narrator turns into prose — the model cannot argue with truth.
- Every turn is versioned, so contradictions are detectable and recoverable.
- Narration is grounded in state deltas, not model memory.

## 7. Roadmap

- **v0.2 LLM layer** — intent parser: free text -> action proposals; narrator:
  state delta -> prose. Provider-agnostic client (OpenAI-compatible), cheap
  model for narration, stronger model for parsing.
- **v0.3 Memory & fact-check** — entity cards + rolling summaries + a judge
  pass that re-verifies narration against the state delta.
- **v0.4 Web UI** — chat panel + live state inspector (the "wow" demo).
- **v0.5 Evaluation** — scripted episodes across three architectures
  (pure-LLM chat, summary memory, EverStory), measuring contradiction rate
  (LLM-judge), memory recall, rule compliance, and cost per turn.
