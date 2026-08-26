# EverStory Multi-Agent Evaluation Report

## Multi-agent investigation benchmark

Overall verdict: **PASS** · Provider: `deepseek-v4-flash+deepseek-v4-flash`

| Metric | Result |
| --- | --- |
| Structured proposal accuracy | 100% (8/8) |
| Approved action success | 100% (8/8) |
| Unauthorized world mutations | 0 |
| Stale proposal safely blocked | yes |
| Evidence grounding | 100% (9/9) |
| Agent challenge messages | 1 |
| Deterministic case completion | yes |
| Investigation memory save/load | pass |
| Serialized investigation memory | 27977 bytes (31 messages / 10 tasks / 9 evidence) |
| Model usage | 12 calls · 9846 tokens · 4308 ms average |

### Per-agent model usage

| Agent | Calls | Prompt tokens | Completion tokens | Total latency |
| --- | --- | --- | --- | --- |
| case_analyst | 2 | 1048 | 401 | 9759 ms |
| case_director | 1 | 742 | 390 | 4883 ms |
| field_investigator | 8 | 4890 | 1574 | 32081 ms |
| skeptic | 1 | 524 | 277 | 4978 ms |

The same scenario runs in offline stub mode for deterministic CI and in API mode
for real per-agent cost and latency measurements. Discussion never receives write
access to world state; only approved typed actions reach the rule engine.
