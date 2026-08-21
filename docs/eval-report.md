# EverStory Evaluation Report

Mode: `stub` (stub = deterministic/offline; api = real LLM numbers)

| Provider | Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
| stub | pure-llm | lost_key | 33% (1/3) | 0 | 0 |
| stub | pure-llm | gift_for_mara | 0% (0/1) | 0 | 0 |
| stub | pure-llm | light_the_lighthouse | 50% (1/2) | 0 | 0 |
| stub | summary-memory | lost_key | 33% (1/3) | 0 | 0 |
| stub | summary-memory | gift_for_mara | 100% (1/1) | 0 | 0 |
| stub | summary-memory | light_the_lighthouse | 0% (0/2) | 0 | 0 |
| stub | everstory | lost_key | 100% (3/3) | 0 | 0 |
| stub | everstory | gift_for_mara | 100% (1/1) | 0 | 0 |
| stub | everstory | light_the_lighthouse | 100% (2/2) | 0 | 0 |

## Provider summary (average recall)

| Provider | Baseline | Avg recall | Tokens |
| --- | --- | --- | --- |
| stub | everstory | 100.0% | 0 |
| stub | pure-llm | 27.8% | 0 |
| stub | summary-memory | 44.4% | 0 |

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
| pure-llm | stub | @10: 0%, @20: 0%, @30: 0% | 0 | n/a |
| summary-memory | stub | @10: 0%, @20: 0%, @30: 0% | 0 | n/a |
| everstory | stub | @10: 100%, @20: 100%, @30: 100% | 0 | n/a |

- Contradiction rate: LLM-judge on consecutive narrations (skipped in stub mode; enable with `--contradictions`).
