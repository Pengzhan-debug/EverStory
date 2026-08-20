# EverStory Evaluation Report

Mode: `api` (stub = deterministic/offline; api = real LLM numbers)

| Provider | Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | lost_key | 67% (2/3) | 0 | 6223 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | gift_for_mara | 0% (0/1) | 0 | 4572 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | light_the_lighthouse | 50% (1/2) | 0 | 13894 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | lost_key | 33% (1/3) | 0 | 4906 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | gift_for_mara | 0% (0/1) | 0 | 3380 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | light_the_lighthouse | 0% (0/2) | 0 | 8545 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | lost_key | 100% (3/3) | 0 | 4297 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | gift_for_mara | 100% (1/1) | 0 | 4761 |
| deepseek-v4-flash+deepseek-v4-flash | everstory | light_the_lighthouse | 100% (2/2) | 0 | 10140 |

## Provider summary (average recall)

| Provider | Baseline | Avg recall | Tokens |
| --- | --- | --- | --- |
| deepseek-v4-flash+deepseek-v4-flash | everstory | 100.0% | 19198 |
| deepseek-v4-flash+deepseek-v4-flash | pure-llm | 38.9% | 24689 |
| deepseek-v4-flash+deepseek-v4-flash | summary-memory | 11.1% | 16831 |

Notes:
- **EverStory** answers fact questions directly from its structured state, so
  recall is exact by construction; its "tokens" reflect narration/parsing only.
- **pure-llm** keeps the full transcript in context; **summary-memory** keeps a
  rolling summary plus recent turns. Both depend on the model's memory.
- Configure `LLM_STRONG_*` / `LLM_CHEAP_*` in `.env` (each role may use a
  different vendor) and run `python -m everstory.eval --mode api` for real
  model numbers.
