# EverStory

**A state-consistent, persistent AI world engine.**

EverStory is a hybrid architecture for long-horizon AI interaction: an LLM
*proposes* actions in natural language, and a deterministic state machine
*decides*. The world — entities, items, locations, relationships, time — lives
in a structured, versioned state graph that the LLM can never directly mutate.
The result: an interactive world that stays consistent for hundreds of turns.

> The core idea: **LLMs are unreliable at remembering and mutating state.
> Don't let them. Separate generation from truth.**

## Why this exists

Every long-horizon LLM application — agents, game NPCs, virtual characters,
roleplay, persistent assistants — eventually contradicts itself, forgets, or
invents state. This project demonstrates a concrete architecture that solves
that problem:

```text
User input
   |
   v
1. Intent parsing   LLM converts "pick up the rusty key" into structured actions
   |
   v
2. Rule validation  The engine checks preconditions against the real world state
   |
   v
3. State update     Deterministic transition (location, ownership, flags, time)
   |
   v
4. Narration        A grounded LLM narrates the *actual* state changes
   |
   v
5. Fact check       Optional judge verifies narration vs. state delta
   |
   v
6. Snapshot         Versioned world state: rollback and branching for free
```

## Current status (v0.1)

- Declarative world definitions (TOML): entities, locations, items, quests
- Rule engine with typed checks and effects (`move`, `take`, `give`, `use`,
  `open`, `talk`, `wait`)
- Deterministic state transitions + per-turn versioned snapshots with rollback
- A playable demo world: **The Lost Lighthouse**
- Interactive CLI (LLM-free structured commands in v0.1; LLM layer in v0.2)

## Quick start

```bash
python -m everstory            # play the demo world
python -m unittest discover -s tests -v   # run the test suite
```

Try: `look`, `move to lighthouse_ground`, `move to cliff_path`, `move to cave`,
`take rusty key`, `use rusty key on chest`, `open chest`, `rollback 0`.

## Roadmap

- **v0.2** — LLM intent parser + grounded narration (Qwen/DeepSeek)
- **v0.3** — memory layer: entity cards, rolling summaries, fact-check pass
- **v0.4** — web UI with a live world-state inspector
- **v0.5** — evaluation harness: EverStory vs. pure-LLM vs. summary-memory
  baselines, with contradiction-rate and recall metrics

## License

MIT
