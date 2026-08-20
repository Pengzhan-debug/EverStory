# EverStory Evaluation Report

Mode: `stub` (stub = deterministic/offline; api = real LLM numbers)

| Baseline | Episode | Recall | Rejected actions | Tokens |
| --- | --- | --- | --- | --- |
| pure-llm | lost_key | 33% (1/3) | 0 | 0 |
| pure-llm | gift_for_mara | 0% (0/1) | 0 | 0 |
| pure-llm | light_the_lighthouse | 50% (1/2) | 0 | 0 |
| summary-memory | lost_key | 33% (1/3) | 0 | 0 |
| summary-memory | gift_for_mara | 100% (1/1) | 0 | 0 |
| summary-memory | light_the_lighthouse | 0% (0/2) | 0 | 0 |
| everstory | lost_key | 100% (3/3) | 0 | 0 |
| everstory | gift_for_mara | 100% (1/1) | 0 | 0 |
| everstory | light_the_lighthouse | 100% (2/2) | 0 | 0 |

Notes:
- **EverStory** answers fact questions directly from its structured state, so
  recall is exact by construction; its "tokens" reflect narration/parsing only.
- **pure-llm** keeps the full transcript in context; **summary-memory** keeps a
  rolling summary plus recent turns. Both depend on the model's memory.
- Run `python -m everstory.eval --mode api` (with `LLM_API_KEY` set) for real
  model numbers.
