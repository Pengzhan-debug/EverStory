# EverStory

**A state-consistent, persistent multi-agent AI world engine — v1.3 identity-core release.**

> [中文版 README](README.zh-CN.md)

[![CI](https://github.com/Pengzhan-debug/EverStory/actions/workflows/ci.yml/badge.svg)](https://github.com/Pengzhan-debug/EverStory/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-141%20passing-22C55E)
![License](https://img.shields.io/badge/license-MIT-0F172A)

[Play the live demo](https://everstory.onrender.com/) · [Architecture](docs/architecture.md) · [Live benchmark](reports/agent-routing-evaluation-zh.md) · [Deployment](docs/DEPLOYMENT.md) · [Identity/BYOK design](docs/IDENTITY_AND_BYOK_DESIGN.md) · [Interview demo](docs/DEMO.md) · [Resume template](docs/RESUME.md)

> The public Render demo runs in deterministic Stub mode for predictable cost. Its verified runtime uses PostgreSQL for durable tenant data and Redis/Valkey for session coordination. Free instances can take up to about a minute to wake after inactivity.

EverStory is a hybrid architecture for long-horizon AI interaction: an LLM *proposes* actions in natural language, while a deterministic state machine *decides*. The world — entities, items, locations, relationships, time, flags and quests — lives in a structured, versioned state graph that the LLM can never directly mutate.

The current web experience turns that engine into **The Lost Lighthouse**, a cinematic multi-agent investigation: players act as Lead Investigator, specialist agents debate and challenge hypotheses, and only player-approved checks can promote engine-backed observations into confirmed evidence.

> **The core idea:** LLMs are unreliable at remembering and mutating state. **Don't let them. Separate generation from truth.**

## 📷 Product tour

![EverStory product loop](docs/assets/readme/everstory-demo.gif)

The demo above is generated from checked-in product captures with
`python scripts/build_demo_gif.py`, so the repository preview is reproducible.

### Cinematic, state-aware game interface

![EverStory gameplay overview](docs/assets/readme/gameplay-overview.png)

The current location owns the screen while the authoritative HUD exposes only the facts needed to act: location, active lead, visible objects, suggested actions, world time and turn. Players can use natural language instead of learning a command grammar.

### Named multi-agent investigation room

![Named investigation agents debating in the team chat](docs/assets/readme/agent-team-chat.png)

Named agents have distinct roles and model routes. They can reply to and challenge one another, while their conclusions remain hypotheses. Structured actions stay pending until the human Lead Investigator approves them.

### Engine-confirmed case board

![Case board with engine-confirmed evidence](docs/assets/readme/case-evidence-board.png)

Approved checks create evidence with type, location, source agent, task link and confirmation turn. Open actions remain visibly separated from confirmed observations.

### Per-agent model routing and diagnostics

![EverStory model control console](docs/assets/readme/model-control-console.png)

Each investigation and runtime role can use an independent or shared OpenAI-compatible connection. Hosted defaults are visibly separated from player-owned BYOK connections: personal-route failures never fall through to the platform key. The console includes per-session quotas, time-bucketed token/request/cost/latency charts, connection tests, and source-aware call logs without returning stored API keys to the browser.

## ✨ What EverStory is now

- **Deterministic AI world engine** — typed actions are validated against real state before anything changes.
- **Persistent world state** — entities, items, locations, relationships, time, flags, quests and snapshots remain structured and inspectable.
- **Production persistence path** — optional PostgreSQL stores guest users, hashed auth sessions, tenant-owned runtime snapshots, save games, an idempotent LLM usage ledger, and AES-256-GCM envelope-encrypted account BYOK profiles; Redis supplies session TTL, mutation quotas, and cross-process player locks.
- **Guest-to-account and cross-device resume** — email one-time codes upgrade or merge a guest without reloading the case; verified players can list and resume only their own investigations across browsers. Double-submit CSRF, auth rotation, device listing/revocation, hashed challenges, and SMTP/development delivery modes protect the account boundary.
- **Natural-language gameplay** — players can say things like `walk toward the lighthouse`, `take the rusty key`, or `talk to the keeper` instead of learning a command language.
- **Grounded narration** — the LLM narrates the state transition that the engine actually applied.
- **Fact checking** — generated narration is checked against the state delta and can be retried when it contradicts the world.
- **Cinematic web UI** — The Lost Lighthouse theme adds atmospheric ocean, fog, lighthouse beacon, storm particles, cinematic transitions, story HUD and immersive input.
- **Multi-agent investigation room** — a Director, Field Investigator, Analyst and Skeptic discuss the case with distinct identities and can challenge one another.
- **Human-in-the-loop action approval** — agents propose typed `travel`, `interview`, `examine`, and `accuse` actions; critical evidence examination and formal accusations cannot bypass the Investigation Room, and every approved action is revalidated by the deterministic engine.
- **Case evidence board** — confirmed scenes, objects and people remain separate from agent hypotheses and survive save/load.
- **Complete mystery loop** — the player washes ashore, gathers three testimonies and three physical/timeline links, requests analyst corroboration, restores the lighthouse, and reaches one deterministic culprit/confession ending.
- **Model usage console** — route each agent between read-only platform defaults and isolated player BYOK connections; inspect quota, stacked usage charts, estimated cost, latency, failures, and source-aware call logs.
- **Hosted-model safety rails** — public guests remain on Stub until account verification; Redis atomically enforces account/day platform Token budgets, preflight reservation/actual-usage settlement, and per-provider failure circuit breakers. Personal BYOK never consumes the platform budget.
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

### Docker (fastest)

```bash
docker compose up --build
# open http://127.0.0.1:8123
```

Compose starts the web service, PostgreSQL 16, and Redis 7 with health checks
and persistent volumes. The app still defaults to deterministic Stub mode.
Copy `.env.example` to `.env` and set `LLM_MODE=api` only when you want live
model calls.

### Local Python

```bash
# 0. Create a virtual environment and install the project
python -m venv everstory-env
everstory-env\Scripts\activate        # Windows
# source everstory-env/bin/activate   # macOS/Linux

pip install -e ".[web,production]"

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

The suite includes a full offline acceptance path: agent-proposed travel, three interviews, three evidence examinations, analyst corroboration, and an evidence-gated final accusation. It requires no API key.

### Try the world

```text
look
move to cottage
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

# Hosted token allowance for each browser runtime; 0 disables the limit.
PLATFORM_SESSION_TOKEN_LIMIT=50000

LLM_STRONG_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_STRONG_API_KEY=sk-...
LLM_STRONG_MODEL=qwen-plus

LLM_CHEAP_BASE_URL=https://api.deepseek.com/v1
LLM_CHEAP_API_KEY=sk-...
LLM_CHEAP_MODEL=deepseek-chat
```

The strong role (intent parsing + consistency judging) and the cheap role (narration) are independent, so vendors can be mixed freely. Restart the server after editing `.env` because configuration is read at startup.

Platform credentials come only from the server environment and are read-only in the browser. A player can add a personal connection in `/settings`; its key is never returned by the settings API, has separate accounting, and is never used as a fallback target. Guests keep personal keys only in the current process. With `DATABASE_URL` and `BYOK_MASTER_KEY`, verified accounts restore model routes and envelope-encrypted BYOK profiles across browsers and restarts; plaintext keys are excluded from runtime JSON, usage records and browser responses. The built-in provider uses an environment-held master key with key IDs and a previous-key ring; a managed cloud KMS adapter remains a production-hardening option.

### PostgreSQL and Redis

`DATABASE_URL` enables the SQLAlchemy storage backend. PostgreSQL then owns
guest users and hashed auth sessions, live game/runtime snapshots, named saves,
and the append-only LLM usage ledger. Every database access is scoped by both
the authenticated `user_id` and active runtime id. `REDIS_URL` enables session TTL markers, fixed-window mutation
rate limiting, and per-session distributed locks. If either variable is blank,
the corresponding local fallback remains available.

```ini
DATABASE_URL=postgresql+psycopg://everstory:password@postgres:5432/everstory
REDIS_URL=redis://redis:6379/0
BYOK_MASTER_KEY=<at-least-32-random-characters>
BYOK_MASTER_KEY_ID=prod-v1
BYOK_PREVIOUS_MASTER_KEYS={}
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

Schema changes are tracked with Alembic (`alembic upgrade head`). Email-code
account login is available when SMTP is configured; the Render blueprint keeps
delivery disabled until the owner supplies it. Migration `20260902_0004` adds
account model profiles. Each personal-connection payload uses a fresh random
data key and AES-256-GCM nonce; the data key is separately wrapped by the active
master-key version and bound to the account id as authenticated data.

The checked-in Render Blueprint provisions a free web service, free PostgreSQL,
and free Key Value cache, then runs Alembic before the web process starts. This
is a portfolio-demo topology: Render's free PostgreSQL expires after 30 days and
has no backups, while free Key Value is intentionally non-persistent. Upgrade
the database before treating the public URL as a long-lived service.

The optional Volcengine Ark catalog uses one shared Base URL and a separate API credential for each of its seven named models. The empirically selected route map uses DeepSeek V4 Pro for directing, Doubao Seed 2.0 Lite for field work, intent parsing and NPC dialogue, GLM 5.3 for analysis, Kimi K2.7 Code for skeptical review, DeepSeek V4 Flash for consistency checks, and MiniMax M3 for narration. Run `python -m scripts.test_model_connections` for a credential-safe health check, or `python -m scripts.run_full_agent_evaluation` for the checkpointed benchmark. Verify the Coding Plan usage rules before using its coding-only endpoint for a non-coding game workload; a standard Ark model API or agent-oriented plan is the safer production choice.

## 🖥️ Web UI structure

```text
everstory/api/static/
  index.html       immersive game shell and HUD
  app.js           authoritative DOM rendering
  gameplay-core.js turn lifecycle, streaming, persistence and recovery
  team-chat.js    multi-agent discussion, task approval and evidence board
  team-chat.css   investigation-room and case-board visual system
  settings.html   BYOK routing, quota, usage chart, and diagnostics console
  style-v5.css     primary visual system
  immersive.css    cinematic overlays and atmosphere
  ui-tweaks.css    investigation layout and responsive polish
  immersive.js     location scenes, inventory and presentation effects
  img/scenes/      compressed location-specific WebP scene art
```

The browser layer is intentionally separated from the engine. The backend remains authoritative; visual state can be upgraded independently. Save files bundle world state with investigation memory while keeping the two domains explicitly separated.

## 📊 Evaluation

EverStory includes an evaluation harness that runs the same scripted episodes against three architectures — pure-LLM, summary-memory, and EverStory — measuring recall, rejection and token metrics. A second deterministic multi-agent benchmark measures proposal accuracy, approval safety, evidence grounding, stale-task rejection, memory persistence, case completion, and real per-agent token/latency usage in API mode.

The current live Ark benchmark covers **8 roles, 23 role/model combinations,
69 fixed role cases, 6 cross-agent exchange chains, and 3 complete cases**.
The selected routes average **98.8%** with a **93.3%** minimum role score;
information transfer, provenance retention, poison rejection, proposal
accuracy, evidence grounding, and case completion all scored **100%**. The
final comparable dataset contains 123 live calls and 118,513 tokens.

| Signal | Result |
| --- | ---: |
| Recommended-route average | **98.8%** |
| Minimum role score | **93.3%** |
| Transfer / provenance / poison rejection | **100% / 100% / 100%** |
| Proposal / evidence / case completion | **100% / 100% / 100%** |
| Live comparable calls | **123** |
| Live tokens | **118,513** |

See:

- [Architecture](docs/architecture.md)
- [Evaluation report](docs/eval-report.md)
- [Multi-agent investigation report](docs/eval-report-team.md)
- [Live multi-agent model report](reports/eval-multi-agent-live.md)
- [Full agent routing and exchange report (Chinese)](reports/agent-routing-evaluation-zh.md)
- [Learned rules](docs/learned-rules.md)
- [Interview demo](docs/DEMO.md)
- [Resume bullets and scope](docs/RESUME.md)
- [Public demo deployment](docs/DEPLOYMENT.md)
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
