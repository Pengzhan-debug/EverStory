# EverStory Evaluation Report

Mode: `api` (stub = deterministic/offline; api = real LLM numbers)

| Provider | Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | lost_key | 67% (2/3) | 0 | 6754 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | gift_for_mara | 0% (0/1) | 0 | 4489 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | light_the_lighthouse | 50% (1/2) | 0 | 16888 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | lost_key | 67% (2/3) | 0 | 4935 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | gift_for_mara | 0% (0/1) | 0 | 3283 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | light_the_lighthouse | 50% (1/2) | 0 | 9078 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | lost_key | 100% (3/3) | 0 | 4138 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | gift_for_mara | 100% (1/1) | 0 | 4080 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | light_the_lighthouse | 100% (2/2) | 0 | 8951 |

## Provider summary (average recall)

| Provider | Baseline | Avg recall | Tokens |
| --- | --- | --- | --- |
| deepseek-v4-flash+deepseek-v4-flash | everstory | 100.0% | 17169 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | 38.9% | 28131 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | 38.9% | 17296 |

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
| pure-llm | deepseek-v4-flash+deepseek-v4-flash | @20: 33%, @40: 0%, @60: 0% | 169111 | n/a |
| summary-memory | deepseek-v4-flash+deepseek-v4-flash | @20: 33%, @40: 0%, @60: 33% | 39477 | n/a |
| everstory | deepseek-v4-flash+deepseek-v4-flash | @20: 100%, @40: 100%, @60: 100% | 36937 | n/a |

- Contradiction rate: LLM-judge on consecutive narrations (skipped in stub mode; enable with `--contradictions`).
