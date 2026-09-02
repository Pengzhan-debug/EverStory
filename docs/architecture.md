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

Every team message carries `claim_type`, `evidence_ids`, `confidence`,
`world_turn`, `status`, and `reply_to`. Confirmed observations are rendered
from the authoritative evidence board; hypotheses and challenges remain
non-authoritative. Each responding agent receives the current world summary,
the shared case board, and a bounded recent transcript, making provenance
retention and cross-agent reply links directly measurable.

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

## 9. Model credential and usage boundary

```text
agent role -> immutable route snapshot -> exactly one connection
                                      |-> platform credential + session quota
                                      `-> player BYOK + separate accounting
```

- Platform connections are created from server environment variables and are
  read-only to the player settings API.
- New browser-configured connections are always classified as `personal`; a
  failed personal request retries only the same endpoint and never falls back
  to a platform credential.
- Every live call records timestamp, agent, connection, credential source,
  model, prompt/completion tokens, estimated cost, latency, result, and a
  bounded error summary. The browser receives no raw key.
- Separate HttpOnly cookies identify a server-issued guest auth session and the
  active game runtime. PostgreSQL stores only the auth-token hash, rejects a
  runtime owned by another user, and scopes runtime, save, and usage queries by
  both `user_id` and runtime id. The in-memory/file fallback remains available.
- With `REDIS_URL`, Redis tracks session TTL, enforces an atomic fixed-window
  mutation quota, and serializes writes to the same player session across
  processes. A local lock/rate-bucket fallback keeps development deterministic.
- Email one-time codes upgrade a guest in place or transactionally move its
  runtimes, saves, and usage to an existing account. Challenges store only the
  email hash and a server-keyed code HMAC; Redis limits email/IP requests.
- Verified accounts can list compact summaries for their owned runtimes and
  explicitly resume one across browsers. The server persists the current case
  and rechecks target ownership before rotating the active-runtime cookie.
- Cookie-authenticated writes use a readable CSRF cookie plus an
  `X-CSRF-Token` header, while login and privilege changes rotate both secrets.
- API credentials are intentionally excluded from runtime documents. Verified
  account profiles use per-save random data keys, AES-256-GCM authenticated
  encryption, account-bound AAD, and a versioned environment master-key ring.
  Full production scale still benefits from a cloud KMS adapter, IP/account
  budget policies, and stateless multi-instance cache invalidation.

## 10. Runtime persistence topology

```text
everstory_auth (server-issued secret) ---> PostgreSQL users/auth_sessions
everstory_runtime (active game id) ------> ownership check
        |
        v
FastAPI runtime cache ---- Redis TTL / rate limit / runtime lock
        |
        +---- PostgreSQL player_sessions (authoritative live snapshot)
        +---- PostgreSQL save_games      (named immutable saves)
        +---- PostgreSQL llm_usage_events (idempotent usage ledger)
        `---- PostgreSQL user_llm_profiles (envelope-encrypted BYOK)
```

The database schema is versioned with Alembic. PostgreSQL JSONB keeps the
versioned world document intact while indexed relational columns retain tenant,
time, turn, and usage query boundaries.

## 11. Empirical routing and evaluation

`python -m scripts.run_full_agent_evaluation` evaluates 8 runtime/team roles
against 23 candidate assignments, then runs evidence-transfer, stale-fact,
poison-rejection, and repeated end-to-end case tests. Phase checkpoints make
the live benchmark resumable; `--refresh-team` reuses role/exchange results and
reruns only the final routed cases. Raw outputs, errors, latency, tokens, and
the generated report are stored under `reports/`.

The checked-in run selected DeepSeek V4 Pro (Director), Doubao Seed 2.0 Lite
(Field/Intent/NPC), GLM 5.3 (Analyst), Kimi K2.7 Code (Skeptic), DeepSeek V4
Flash (Judge), and MiniMax M3 (Narrator). See
[`reports/agent-routing-evaluation-zh.md`](../reports/agent-routing-evaluation-zh.md).
