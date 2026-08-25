# EverStory Multi-Agent Evaluation Report

## Multi-agent investigation benchmark

Overall verdict: **PASS** · Provider: `stub`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | 100% (6/6) |
| Approved action success | 100% (6/6) |
| Unauthorized world mutations | 0 |
| Stale proposal safely blocked | yes |
| Evidence grounding | 100% (6/6) |
| Agent challenge messages | 1 |
| Deterministic case completion | yes |
| Investigation memory save/load | pass |
| Serialized investigation memory | 18086 bytes (22 messages / 7 tasks / 6 evidence) |
| Model usage | 0 calls · 0 tokens · 0 ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
| offline deterministic path | 0 | 0 | 0 | 0 ms |

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.
