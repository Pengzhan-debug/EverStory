# EverStory resume and interview notes

## One-line project description

Built a state-consistent multi-agent investigation game in which LLM agents
propose and challenge actions while a deterministic world engine owns truth,
validation, evidence provenance, persistence, and endings.

## Resume-ready bullets

- Designed a hybrid LLM/state-machine architecture that converts natural
  language into typed actions and prevents models from directly mutating
  authoritative entities, inventory, locations, quests, time, and flags.
- Built a human-in-the-loop investigation workflow with four routed agents,
  mutual challenges, structured task approval, stale-task rejection, and a
  seven-link evidence gate for deterministic case resolution.
- Implemented FastAPI + SSE streaming, per-agent OpenAI-compatible model
  routing, bilingual UI, save/load of world and conversation memory, and a
  cinematic responsive web client in vanilla JavaScript/CSS.
- Created offline CI and live-model evaluation: 91 deterministic tests plus a
  DeepSeek run with 100% proposal accuracy (8/8), 100% approved-action success
  (8/8), 100% evidence grounding (9/9), and zero unauthorized world mutations.

## 30-second technical explanation

The key boundary is “LLM proposes, state machine decides.” Conversation agents
can form hypotheses, but they receive no write access. Evidence examination and
formal accusation are routed through a player-approved task protocol. The rule
engine executes typed actions, records a state hash and event, and only then
allows the model to narrate the confirmed transition. That makes hallucination
containment measurable rather than prompt-only.

## Honest scope

EverStory v1.0 is a polished, locally deployable portfolio release, not a
production multiplayer service. Sessions and API credentials are process-local;
a public multi-instance deployment would need durable storage, authentication,
rate limiting, and a secret manager.
