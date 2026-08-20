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
- Configure providers in `.env` (`LLM_PROVIDERS=qwen,deepseek` + per-provider
  keys) and run `python -m everstory.eval --mode api` for real model numbers.
