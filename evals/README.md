# evals/

Retrieval evaluation for the Qdrant knowledge base.

| File | Contents |
|---|---|
| `noavia_rag_eval.py` | The evaluation harness |
| `noavia_rag_eval.jsonl` | Query set: supported queries the KB should answer, plus unsupported controls it should not |
| `noavia_rag_eval_results.json` | Recorded scores from the last run |

## Why this exists

It calibrated `rag_min_score`, the similarity threshold applied in
`Collect RAG Matches` after retrieval.

Measured against this set, **supported queries score 0.14 to 0.50 and unsupported
queries score 0.** The threshold sits at **0.1**, in the gap between them.

That number looks arbitrarily low until you see the distribution. The absolute values
are small because the corpus is small and the queries are short; what matters is
separation, not magnitude. When nothing clears the threshold the draft prompt is
instructed to include the exact sentence the task requires about no specific policy
being found.

## Known gap

This ran once, manually. It should be a golden set asserted in CI so that re-chunking
or a prompt change cannot silently regress retrieval. That is item 1 on the "what I
would improve" list in the submission README.
