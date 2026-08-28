# EverStory v1.1 status and roadmap

EverStory v1.1 is a GitHub- and resume-ready local portfolio release. It is a
complete single-case game and engineering demonstration, not yet a production
multiplayer service.

## v1.1 acceptance status

- [x] Storm Shore narrative opening with clear onboarding
- [x] Deterministic world state, typed actions, validation, snapshots/rollback
- [x] Grounded narration, language guard, and consistency checking
- [x] Named four-agent investigation chat with mutual challenges
- [x] Player-approved travel, interview, examination, review, and accusation
- [x] Main chat cannot bypass critical evidence or accusation approval
- [x] Six primary evidence links plus Case Analyst corroboration gate
- [x] Unified ending requires case resolution, lighthouse restoration, and secret
- [x] Conversation, team tasks, evidence, and world state survive save/load
- [x] Per-agent OpenAI-compatible routing, tests, latency, Token diagnostics
- [x] Shared Chinese/English UI and model-output language enforcement
- [x] 102 deterministic tests on Python 3.11/3.12 CI
- [x] Live multi-model Ark benchmark with per-agent cost/latency metrics
- [x] Docker/Compose, Render blueprint, demo GIF, screenshots, resume notes

## Verified v1.1 measurements

- Structured task proposal accuracy: 100% (8/8)
- Approved action success: 100% (8/8)
- Evidence grounding: 100% (9/9)
- Unauthorized world mutations: 0
- Role/model matrix: 8 roles, 23 combinations, 69 fixed role cases
- Cross-agent evaluation: 6 exchange chains and 3 complete cases
- Recommended-route average: 98.8%; minimum role score: 93.3%
- Transfer, provenance, poison rejection, evidence, completion: 100%
- Comparable real model usage: 123 calls, 118,513 tokens

See `reports/agent-routing-evaluation-zh.md` and the checked-in JSON/checkpoints
for the reproducible report.

## Production roadmap (not claimed as implemented)

1. Replace process-local sessions and settings with Postgres/Redis storage.
2. Add authentication, per-user quotas, server-side secret storage, and rate limits.
3. Add browser-level Playwright CI for the full bilingual investigation path.
4. Add branching cases and authoring tools for declarative TOML worlds.
5. Compare the four-agent workflow with a controlled single-agent baseline on
   solve rate, contradiction rate, cost, and player-rated usefulness.

## Honest limitations

- One mystery has the fully authored multi-agent ending; Ghost Train remains an
  engine-content example rather than an equally polished campaign.
- Runtime sessions are process-local and capped, so horizontal scaling is not
  safe without durable shared storage.
- Live model quality and latency depend on the configured provider.
- The checked-in Render blueprint defaults to offline Stub mode; a live public
  deployment still needs the owner's provider key and operational safeguards.
