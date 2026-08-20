# EverStory

**A state-consistent, persistent AI world engine.**

EverStory is a hybrid architecture for long-horizon AI interaction: an LLM
*proposes* actions in natural language, and a deterministic state machine
*decides*. The world — entities, items, locations, relationships, time — lives
in a structured, versioned state graph that the LLM can never directly mutate.
The result: an interactive world that stays consistent for hundreds of turns.

> The core idea: **LLMs are unreliable at remembering and mutating state.
> Don't let them. Separate generation from truth.**

## What's included

- **v0.1 — Engine core**: declarative rule DSL (`move`, `take`, `give`, `use`,
  `open`, `talk`, `wait`), deterministic state transitions, per-turn versioned
  snapshots with rollback.
- **v0.2 — LLM layer**: provider-agnostic client (stub/offline or any
  OpenAI-compatible API), free-text intent parsing, grounded narration.
- **v0.3 — Memory & fact-check**: entity cards + rolling summaries + a
  consistency judge that re-verifies narration against the state delta.
- **v0.4 — Web UI**: FastAPI + a live world inspector with an SVG map,
  inventory, item/character states, quests, and an event log.
- **v0.5 — Evaluation harness**: the same scripted episodes run against three
  architectures — pure-LLM, summary-memory, and EverStory — with recall,
  rejection, and token metrics, plus a generated report.
- **v1.1 — Symbolic world-model induction**: dynamics rules are *learned* from
  `(state, action, next-state)` trajectories (greedy conjunctive learning over
  role-abstracted predicates), verified against a held-out episode, and
  rendered as human-readable rules with counterfactual checks.
- A playable demo world: **The Lost Lighthouse** (fully declarative TOML).

## Architecture

```text
User input (natural language)
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
5. Fact check       A judge verifies narration vs. state delta; retry if not
   |
   v
6. Snapshot         Versioned world state: rollback and branching for free
```

The LLM never holds or mutates state — it is handed a *rendering* of the state
each turn, proposes typed actions, and narrates the delta the engine actually
applied. See [docs/architecture.md](docs/architecture.md) for the full design.

## Quick start

```bash
# 0. Create a virtual environment and install the project
python -m venv everstory-env
everstory-env\Scripts\activate        # Windows (source everstory-env/bin/activate on macOS/Linux)
pip install -e ".[web]"

# 1. Play in the terminal (deterministic stub mode, no API key needed)
everstory

# 2. Web UI with live world inspector
everstory-serve            # or: python -m uvicorn everstory.api.main:app --port 8123
# open http://127.0.0.1:8123

# 3. Run the evaluation benchmark (stub mode = offline deterministic)
everstory-eval --mode stub

# 4. Run the test suite
python -m unittest discover -s tests -v

# 5. Learn world dynamics from trajectories (symbolic world-model induction)
everstory-learn            # or: python -m everstory.learn
```

### Try it

```text
look
move to lighthouse_ground
move to cliff_path
move to cave
take rusty key
use rusty key on chest
open chest
take flint
rollback 0
```

## Real LLM numbers

By default EverStory runs in `stub` mode: deterministic, offline, and
test-friendly. To use real models (Qwen / DeepSeek / any OpenAI-compatible
endpoint):

```bash
cp .env.example .env     # edit: LLM_MODE=api and LLM_API_KEY=...
# restart the server after editing .env (it is read at startup)
everstory-serve
python -m everstory.eval --mode api
```

The eval report (`docs/eval-report.md`) then contains genuine model numbers for
the three-architecture comparison.

## Cross-provider benchmark

Compare the same episodes across vendors (Qwen, DeepSeek, ...) in one run:

```bash
# .env: uncomment LLM_PROVIDERS=qwen,deepseek and fill each provider's key
python -m everstory.eval --mode api --providers qwen,deepseek
```

The report gains a provider column and an average-recall summary per provider,
so you can show which model family retains world state best over long horizons.

## Mix roles across vendors

The strong role (intent parsing + consistency judging) and the cheap role
(narration) do not have to come from the same vendor:

```bash
# .env: define providers, then route roles
# LLM_PROVIDERS=qwen,deepseek
# LLM_ROLE_STRONG=qwen
# LLM_ROLE_CHEAP=deepseek
```

The web UI then parses intents with Qwen and narrates with DeepSeek (or any
combination). Benchmark the mix as a single run:

```bash
python -m everstory.eval --mode api --role-mix
```

## Interview demo

[docs/DEMO.md](docs/DEMO.md) is a 1-minute demo script with talking points and
likely follow-up questions — walk it once before an interview.

## Repository layout

```text
everstory/
  engine.py        deterministic rule engine + WorldSession (rollback/snapshots)
  trajectory.py    transition recording + role-abstracted fact extraction
  models.py        entity/relationship/action/state domain models
  commands.py      structured command parser (CLI + stub intent)
  pipeline.py      turn pipeline: intent -> engine -> narration -> fact-check
  llm/             provider client, intent parser, narrator, consistency judge
  memory/          entity cards, rolling summaries, context builder
  api/             FastAPI app + static web UI (chat + world inspector)
  eval/            three-architecture benchmark + report generator
  learn/           rule induction from trajectories + learned-rules report
  worlds/          declarative TOML worlds (demo: The Lost Lighthouse)
docs/architecture.md   design document
docs/eval-report.md    generated benchmark report
docs/learned-rules.md  induced dynamics rules report
```

## Why this is interesting

Long-horizon LLM applications — agents, game NPCs, virtual characters, roleplay,
persistent assistants — all suffer from the same failure: models forget,
contradict themselves, and invent state. EverStory is a concrete, tested answer
to that problem, built as a small engine rather than a wrapper: the world is
truth, the LLM is a constrained actor, and every claim can be verified.

## License

MIT
