# EverStory

**A state-consistent, persistent AI world engine — now presented as an immersive AI RPG.**

> [中文版 README](README.zh-CN.md)

EverStory is a hybrid architecture for long-horizon AI interaction: an LLM *proposes* actions in natural language, while a deterministic state machine *decides*. The world — entities, items, locations, relationships, time, flags and quests — lives in a structured, versioned state graph that the LLM can never directly mutate.

The current web experience turns that engine into **The Lost Lighthouse**, a cinematic multi-agent investigation: players act as Lead Investigator, specialist agents debate and challenge hypotheses, and only player-approved checks can promote engine-backed observations into confirmed evidence.

> **The core idea:** LLMs are unreliable at remembering and mutating state. **Don't let them. Separate generation from truth.**

## 📷 Product tour

### Cinematic, state-aware game interface

![EverStory gameplay overview](docs/assets/readme/gameplay-overview.png)

The current location owns the screen while the authoritative HUD exposes only the facts needed to act: location, active lead, visible objects, suggested actions, world time and turn. Players can use natural language instead of learning a command grammar.

<table>
  <tr>
    <td width="50%">
      <img src="docs/assets/readme/agent-team-chat.png" alt="Named investigation agents debating in the team chat">
      <br><strong>Multi-agent investigation room</strong><br>
      Named agents have distinct roles and model routes. They can reply to and challenge one another, while their conclusions remain hypotheses. Structured actions stay pending until the human Lead Investigator approves them.
    </td>
    <td width="50%">
      <img src="docs/assets/readme/case-evidence-board.png" alt="Case board with engine-confirmed evidence">
      <br><strong>Engine-confirmed case board</strong><br>
      Approved checks create evidence with type, location, source agent, task link and confirmation turn. Open actions remain visibly separated from confirmed observations.
    </td>
  </tr>
</table>

### Per-agent model routing and diagnostics

![EverStory model control console](docs/assets/readme/model-control-console.png)

Each investigation and runtime role can use an independent or shared OpenAI-compatible connection. The standard console also provides connection tests, latency, token and failure diagnostics without returning stored API keys to the browser.

## ✨ What EverStory is now

- **Deterministic AI world engine** — typed actions are validated against real state before anything changes.
- **Persistent world state** — entities, items, locations, relationships, time, flags, quests and snapshots remain structured and inspectable.
- **Natural-language gameplay** — players can say things like `walk toward the lighthouse`, `take the rusty key`, or `talk to the keeper` instead of learning a command language.
- **Grounded narration** — the LLM narrates the state transition that the engine actually applied.
- **Fact checking** — generated narration is checked against the state delta and can be retried when it contradicts the world.
- **Cinematic web UI** — The Lost Lighthouse theme adds atmospheric ocean, fog, lighthouse beacon, storm particles, cinematic transitions, story HUD and immersive input.
- **Multi-agent investigation room** — a Director, Field Investigator, Analyst and Skeptic discuss the case with distinct identities and can challenge one another.
- **Human-in-the-loop action approval** — agents propose typed `travel`, `interview`, `examine`, and `accuse` actions; nothing changes until the player approves, then the deterministic engine validates and executes the action.
- **Case evidence board** — confirmed scenes, objects and people remain separate from agent hypotheses and survive save/load.
- **Complete mystery loop** — three suspects, contradictory testimony, physical clues, evidence-gated accusations, and a deterministic culprit/confession make the lighthouse case solvable rather than merely conversational.
- **Model signal console** — configure multiple OpenAI-compatible providers, route each agent independently, test connections, and inspect latency/token diagnostics.
- **Shared Chinese / English interface** — the game shell and model console share one locale preference; HUD, maps, objectives, known items and the investigation room update immediately without changing engine IDs.
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
- 🗼 location-specific cinematic scene art
- 🌫 fog, storm and rain atmosphere
- 🎬 cinematic story transitions
- ✍️ live natural-language story input
- 🧭 live location / turn / time HUD
- 🗺 interactive case map
- 💬 named multi-agent group chat with mutual challenges
- ✅ player-approved investigation tasks
- 🔎 executable travel / interview / examine / accuse actions
- 🕵️ evidence-gated sabotage mystery and final confrontation
- 🧷 confirmed-evidence case board
- 📡 per-agent API routing and diagnostics console
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
7. Team investigation   Agents debate; player approves grounded checks
        |
        v
8. Presentation         Web UI visualizes story, evidence and world truth
```

The LLM never holds or mutates authoritative state. It receives a rendering of the current state, proposes typed actions, and narrates only after the deterministic engine has decided what actually happened. Team discussion is also non-authoritative: an agent can suggest or challenge, but only an approved deterministic check can create a confirmed evidence record.

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

The suite includes a full offline acceptance path: agent-proposed travel, two interviews, two physical-evidence examinations, and an evidence-gated final accusation. It requires no API key.

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

EverStory can run in deterministic offline Stub mode or Live API mode. The recommended setup is the in-app **Model Console** at `/settings`, where connections can be shared or assigned per agent and tested without exposing stored keys. Environment variables remain available as a deployment fallback:

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
  app.js           authoritative DOM rendering
  gameplay-core.js turn lifecycle, streaming, persistence and recovery
  team-chat.js    multi-agent discussion, task approval and evidence board
  team-chat.css   investigation-room and case-board visual system
  settings.html   model connection/routing/diagnostics console
  style-v5.css     primary visual system
  immersive.css    cinematic overlays and atmosphere
  ui-tweaks.css    investigation layout and responsive polish
  immersive.js     location scenes, inventory and presentation effects
  img/scenes/      compressed location-specific WebP scene art
```

The browser layer is intentionally separated from the engine. The backend remains authoritative; visual state can be upgraded independently. Save files bundle world state with investigation memory while keeping the two domains explicitly separated.

## 📊 Evaluation

EverStory includes an evaluation harness that runs the same scripted episodes against three architectures — pure-LLM, summary-memory, and EverStory — measuring recall, rejection and token metrics. A second deterministic multi-agent benchmark measures proposal accuracy, approval safety, evidence grounding, stale-task rejection, memory persistence, case completion, and real per-agent token/latency usage in API mode.

See:

- [Architecture](docs/architecture.md)
- [Evaluation report](docs/eval-report.md)
- [Multi-agent investigation report](docs/eval-report-team.md)
- [Learned rules](docs/learned-rules.md)
- [Interview demo](docs/DEMO.md)
- [Project status & roadmap](docs/ROADMAP.md)

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
