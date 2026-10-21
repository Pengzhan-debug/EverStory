# EverStory Evaluation Report

Mode: `stub` (stub = deterministic/offline; api = real LLM numbers)

| Provider | Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
| offline-stub | pure-llm | lost_key | 0% (0/3) | 0 | 0 |
| offline-stub | pure-llm | gift_for_mara | 0% (0/1) | 0 | 0 |
| offline-stub | pure-llm | light_the_lighthouse | 0% (0/2) | 0 | 0 |
| offline-stub | summary-memory | lost_key | 0% (0/3) | 0 | 0 |
| offline-stub | summary-memory | gift_for_mara | 0% (0/1) | 0 | 0 |
| offline-stub | summary-memory | light_the_lighthouse | 0% (0/2) | 0 | 0 |
| offline-stub | everstory | lost_key | 100% (3/3) | 0 | 0 |
| offline-stub | everstory | gift_for_mara | 100% (1/1) | 0 | 0 |
| offline-stub | everstory | light_the_lighthouse | 100% (2/2) | 0 | 0 |

## Provider summary (average recall)

| Provider | Baseline | Avg recall | Tokens |
| --- | --- | --- | --- |
| offline-stub | everstory | 100.0% | 0 |
| offline-stub | pure-llm | 0.0% | 0 |
| offline-stub | summary-memory | 0.0% | 0 |

Notes:
- **EverStory** answers fact questions directly from its structured state, so
  recall is exact by construction; its "tokens" reflect narration/parsing only.
- **pure-llm** keeps the full transcript in context; **summary-memory** keeps a
  rolling summary plus recent turns. Both depend on the model's memory.
- Configure `LLM_STRONG_*` / `LLM_CHEAP_*` in `.env` (each role may use a
  different vendor) and run `python -m everstory.eval --mode api` for real
  model numbers.

## Long-horizon memory decay

Same world facts asked at checkpoints while wandering for many turns. Facts never change in this episode, so recall loss is purely a memory/architecture effect.

| Baseline | Provider | Checkpoint recall | Tokens | Contradictions |
| --- | --- | --- | --- | --- |
| pure-llm | offline-stub | @20: 0%, @40: 0%, @60: 0% | 0 | n/a |
| summary-memory | offline-stub | @20: 0%, @40: 0%, @60: 0% | 0 | n/a |
| everstory | offline-stub | @20: 100%, @40: 100%, @60: 100% | 0 | n/a |

- Contradiction rate: LLM-judge on consecutive narrations (skipped in stub mode; enable with `--contradictions`).

## Multi-agent investigation benchmark

Overall verdict: **PASS** · Provider: `offline-stub-repeat-1`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | 100% (8/8) |
| Approved action success | 100% (8/8) |
| Unauthorized world mutations | 0 |
| Stale proposal safely blocked | yes |
| Evidence grounding | 100% (9/9) |
| Agent challenge messages | 1 |
| Structured message coverage | 100% |
| Task-result evidence linkage | 100% |
| Cross-agent reply links | 1 |
| Useful-message ratio | 95% |
| Deterministic case completion | yes |
| Investigation memory save/load | pass |
| Serialized investigation memory | 30274 bytes (31 messages / 10 tasks / 9 evidence) |
| Model usage | 0 calls · 0 tokens · 0 ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
| offline deterministic path | 0 | 0 | 0 | 0 ms |

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.


## Multi-agent investigation benchmark

Overall verdict: **PASS** · Provider: `offline-stub-repeat-2`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | 100% (8/8) |
| Approved action success | 100% (8/8) |
| Unauthorized world mutations | 0 |
| Stale proposal safely blocked | yes |
| Evidence grounding | 100% (9/9) |
| Agent challenge messages | 1 |
| Structured message coverage | 100% |
| Task-result evidence linkage | 100% |
| Cross-agent reply links | 1 |
| Useful-message ratio | 95% |
| Deterministic case completion | yes |
| Investigation memory save/load | pass |
| Serialized investigation memory | 30274 bytes (31 messages / 10 tasks / 9 evidence) |
| Model usage | 0 calls · 0 tokens · 0 ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
| offline deterministic path | 0 | 0 | 0 | 0 ms |

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.


## Multi-agent investigation benchmark

Overall verdict: **PASS** · Provider: `offline-stub-repeat-3`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | 100% (8/8) |
| Approved action success | 100% (8/8) |
| Unauthorized world mutations | 0 |
| Stale proposal safely blocked | yes |
| Evidence grounding | 100% (9/9) |
| Agent challenge messages | 1 |
| Structured message coverage | 100% |
| Task-result evidence linkage | 100% |
| Cross-agent reply links | 1 |
| Useful-message ratio | 95% |
| Deterministic case completion | yes |
| Investigation memory save/load | pass |
| Serialized investigation memory | 30274 bytes (31 messages / 10 tasks / 9 evidence) |
| Model usage | 0 calls · 0 tokens · 0 ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
| offline deterministic path | 0 | 0 | 0 | 0 ms |

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.
