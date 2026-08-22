# EverStory

**A state-consistent, persistent AI world engine — now presented as an immersive AI RPG.**

> [中文版 README](README.zh-CN.md)

EverStory is a hybrid architecture for long-horizon AI interaction: an LLM *proposes* actions in natural language, while a deterministic state machine *decides*. The world — entities, items, locations, relationships, time, flags and quests — lives in a structured, versioned state graph that the LLM can never directly mutate.

The current web experience turns that engine into **The Lost Lighthouse**, a cinematic dark-ocean adventure world: players speak naturally, the engine resolves what is actually true, and the interface visualizes the resulting world state through immersive HUDs, a 3D sea chart, atmospheric effects, inventory, quests, entities and an event log.

> **The core idea:** LLMs are unreliable at remembering and mutating state. **Don't let them. Separate generation from truth.**

## ✨ What EverStory is now

- **Deterministic AI world engine** — typed actions are validated against real state before anything changes.
- **Persistent world state** — entities, items, locations, relationships, time, flags, quests and snapshots remain structured and inspectable.
- **Natural-language gameplay** — players can say things like `walk toward the lighthouse`, `take the rusty key`, or `talk to the keeper` instead of learning a command language.
- **Grounded narration** — the LLM narrates the state transition that the engine actually applied.
- **Fact checking** — generated narration is checked against the state delta and can be retried when it contradicts the world.
- **Cinematic web UI** — The Lost Lighthouse theme adds atmospheric ocean, fog, lighthouse beacon, storm particles, cinematic transitions, story HUD and immersive input.
- **3D world layer** — WebGL/Three.js scene rendering provides a lighthouse, ocean, stars, fog, lighting and camera motion while the world API remains the source of truth.
- **World Inspector** — live turn/time, entities, items, quests, event log and state-oriented debugging remain available without breaking immersion.
- **Inventory & keyboard interaction** — `I` opens inventory, `TAB` focuses world state, `ESC` closes overlays.
- **Playable worlds** — **The Lost Lighthouse** and **The Ghost Train** demonstrate that the engine is generic and data-driven.
- **Evaluation & world-model induction** — compare architectures and learn symbolic dynamics rules from `(state, action, next-state)` trajectories.

## 🎮 The Lost Lighthouse

The primary demo world is now designed as an immersive AI adventure:

```text
                         ✦       🌙

                              🗼
                         THE LIGHTHOUSE
                    ~~~~~~~~~~~~~~~~~~~~~
                  ~~~~~~~~ DARK OCEAN ~~~~~~~~

                  "The storm is getting closer."

                         LIVE STORY

                WHAT WILL YOU DO?
        ┌──────────────────────────────────────┐
        │ > walk toward the lighthouse         │
        └──────────────────────────────────────┘

   LOCATION                 QUESTS              WORLD STATE
   Cliff Path               Keeper's Secret     Turn 27
   Lighthouse               Lost Lantern        Time 21:42
```

The UI is deliberately **not** a conventional SaaS dashboard. The world occupies the screen; HUD panels expose state only when useful. This makes EverStory suitable both as a technical demonstration of state-consistent LLM interaction and as a foundation for an AI-native RPG.

### Current web experience

- 🌊 atmospheric ocean / night background
- 🗼 lighthouse silhouette and animated beacon
- 🌫 fog, storm and particle effects
- 🎬 cinematic story transitions
- ✍️ live natural-language story input
- 🧭 live location / turn / time HUD
- 🗺 interactive 3D sea chart
- 🎒 inventory overlay
- ⚔ quest tracker
- 👥 character & item inspector
- 📜 ship's log / event history
- 💾 save / load / new-world controls
- 📱 responsive layout

## 🧠 Architecture

```text
User input (natural language)
        |
        v
1. Intent parsing       LLM converts natural language into typed actions
        |
        v
2. Rule validation      Engine checks preconditions against real world state
        |
        v
3. State update         Deterministic transition: location/items/flags/time
        |
        v
4. Narration            Grounded LLM narrates the actual state delta
        |
        v
5. Fact check           Judge verifies narration against the state delta
        |
        v
6. Snapshot             Versioned world state enables rollback and branching
        |
        v
7. Presentation         Web UI + 3D scene visualize the resulting world
```

The LLM never holds or mutates authoritative state. It receives a rendering of the current state, proposes typed actions, and narrates only after the deterministic engine has decided what actually happened. The 3D layer follows the world API; it is presentation, not the source of truth.

## 🚀 Quick start

```bash
# 0. Create a virtual environment and install the project
python -m venv everstory-env
everstory-env\Scripts\activate        # Windows
# source everstory-env/bin/activate   # macOS/Linux

pip install -e ".[web]"

# 1. Play in the terminal (deterministic stub mode, no API key needed)
everstory

# 2. Start the immersive web UI
everstory-serve
# or: python -m uvicorn everstory.api.main:app --port 8123

# open http://127.0.0.1:8123

# 3. Run the evaluation benchmark
everstory-eval --mode stub

# 4. Run the test suite
python -m unittest discover -s tests -v

# 5. Learn world dynamics from trajectories
everstory-learn
```

### Try the world

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

In the web UI, you can instead use natural language:

```text
walk toward the lighthouse
examine the keeper
pick up the rusty key
use the rusty key on the chest
wait
```

## ⚙️ Configuration (real LLM mode)

By default EverStory runs in `stub` mode: deterministic, offline, and test-friendly. To use real models, edit `.env` (copied from `.env.example`):

```ini
LLM_MODE=api

LLM_STRONG_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_STRONG_API_KEY=sk-...
LLM_STRONG_MODEL=qwen-plus

LLM_CHEAP_BASE_URL=https://api.deepseek.com/v1
LLM_CHEAP_API_KEY=sk-...
LLM_CHEAP_MODEL=deepseek-chat
```

The strong role (intent parsing + consistency judging) and the cheap role (narration) are independent, so vendors can be mixed freely. Restart the server after editing `.env` because configuration is read at startup.

## 🖥️ Web UI structure

```text
everstory/api/static/
  index.html       immersive game shell and HUD
  app.js           core web UI + API interaction
  style-v5.css     primary visual system
  immersive.css    cinematic overlays and atmosphere
  immersive.js     immersive interactions / inventory / effects
  world3d.js       WebGL 3D world rendering
  world-sync.js    world-state → presentation synchronization
```

The browser layer is intentionally separated from the engine. The backend remains authoritative; visual state can be upgraded independently.

## 📊 Evaluation

EverStory includes an evaluation harness that runs the same scripted episodes against three architectures — pure-LLM, summary-memory, and EverStory — measuring recall, rejection and token metrics. The repository also contains symbolic world-model induction from trajectories and a generated learned-rules report.

See:

- [Architecture](docs/architecture.md)
- [Evaluation report](docs/eval-report.md)
- [Learned rules](docs/learned-rules.md)
- [Interview demo](docs/DEMO.md)

## 🗂 Repository layout

```text
everstory/
  engine.py        deterministic rule engine + WorldSession
  trajectory.py    transition recording + role-abstracted fact extraction
  models.py        entity/relationship/action/state domain models
  commands.py      structured command parser
  pipeline.py      turn pipeline: intent -> engine -> narration -> fact-check
  llm/             provider client, intent parser, narrator, consistency judge
  memory/          entity cards, rolling summaries, context builder
  api/             FastAPI app + immersive web UI
  eval/            three-architecture benchmark + report generator
  learn/           rule induction from trajectories + learned-rules report
  persistence.py   save/load world sessions to JSON
  worlds/          declarative TOML worlds

docs/
  architecture.md
  eval-report.md
  learned-rules.md
  DEMO.md
```

## 💡 Why this is interesting

Long-horizon LLM applications — agents, game NPCs, virtual characters, roleplay, persistent assistants — all suffer from the same failure: models forget, contradict themselves, and invent state.

EverStory takes a different approach:

> **The world is truth. The LLM is a constrained actor. Every important claim can be verified.**

The immersive UI is therefore more than decoration. It is a visualization layer for a persistent, state-consistent AI world: the player sees the story, while the inspector can reveal the exact entities, transitions, quests and events that made the story possible.

## 📜 License

MIT
