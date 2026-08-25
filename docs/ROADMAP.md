# EverStory project status and roadmap

EverStory is currently a strong local portfolio prototype, not a production game service.
This document keeps the public claims testable and makes the remaining work explicit.

## Implemented

- Deterministic world state, typed actions, validation, snapshots and rollback
- Grounded narration plus consistency checking
- Multi-agent investigation chat with named roles and mutual challenges
- Human approval for structured investigation proposals
- Engine-confirmed evidence board with task/source/turn provenance
- Versioned save/load for both world state and investigation memory
- Per-agent OpenAI-compatible API routing, connection tests and diagnostics
- Offline Stub mode and 67 deterministic automated tests
- Responsive cinematic web UI and two declarative worlds
- Evaluation harness and symbolic rule induction from trajectories

## GitHub-ready milestone

- [x] Reproducible offline quick start
- [x] Automated CI on Python 3.11 and 3.12
- [x] License, architecture notes, evaluation reports and interview demo
- [x] No API keys returned to the browser or committed to the repository
- [ ] Add a 60–90 second demo GIF/video and three annotated screenshots
- [ ] Add Docker support or a one-command hosted demo
- [ ] Confirm CI is green on the public repository
- [ ] Add an architecture diagram that includes the investigation agents

## Resume-ready v1 milestone

- [ ] Complete one end-to-end mystery path driven by agent proposals and player approvals
- [ ] Add approved world actions: travel, NPC interview and item examination
- [ ] Evaluate multi-agent value against a single-agent baseline: solve rate, contradiction rate, cost and latency
- [ ] Add long-session tests for chat/task/evidence memory and save compatibility
- [ ] Provide a public demo with safe rate limits and server-side secret management
- [ ] Record a concise technical walkthrough covering tradeoffs and failure cases

## Current limitations

- Agent-approved tasks currently inspect or review authoritative state; they do not autonomously move characters or mutate the world.
- Evidence extraction is deterministic and scene-oriented; richer hypothesis/evidence graphs are planned.
- Runtime sessions are process-local and capped; production deployment needs durable storage and authentication.
- The Live API experience depends on the configured provider's availability and rate limits.

The priority is depth and evidence of engineering judgment—not adding more agents, worlds, or visual effects before the core investigation loop is measurable.
