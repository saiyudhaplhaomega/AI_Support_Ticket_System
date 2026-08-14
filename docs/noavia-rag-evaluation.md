# NOAVIA credential-free RAG evaluation

Run `python3 evals/noavia_rag_eval.py` from the repository root. The 40 labeled
cases cover four variations for each approved knowledge source and eight
unsupported requests. It uses only the deterministic local embedding/store and
writes `evals/noavia_rag_eval_results.json`; it makes no network or model call.

At the measured `0.10` threshold, Recall@3 is 71.88%, Top-1 is 65.62%, MRR is
68.75%, unsupported fallback accuracy is 87.5%, and one unsupported case is a
false-confidence case. The lexical grounding gate prevents most collision-only
answers, but the deterministic hash baseline remains deliberately limited and
does not meet a production-quality retrieval target. The committed result file
is generated from the current fixture and implementation; any improvement (such
as typo-aware normalization, hybrid retrieval, reranking, or metadata filters)
must be measured against the same cases before release use.

For a low-confidence response the required sentence is exactly: `No specific
policy found — this response is based on general knowledge.` The evaluator does
not draft or send a customer reply.
