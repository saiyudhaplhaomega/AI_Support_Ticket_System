# NOAVIA credential-free RAG evaluation

Run `python3 evals/noavia_rag_eval.py` from the repository root. The 40 labeled
cases cover four variations for each approved knowledge source and eight
unsupported requests. It uses only the deterministic local embedding/store and
writes `evals/noavia_rag_eval_results.json`; it makes no network or model call.

At the measured `0.10` baseline threshold, Recall@3 is 84.38%, Top-1 is 65.62%,
MRR is 73.96%, unsupported fallback accuracy is 37.5%, and five unsupported
cases are false-confidence cases. At `0.18`, fallback accuracy improves to
87.5% but Recall@3 falls to 75% and one false-confidence case remains. The
supported and unsupported score distributions overlap, so no threshold meets
all release targets. The committed fixture preserves this measured baseline;
the smallest justified follow-up is deterministic typo-aware lexical
normalization, measured against the same cases before considering hybrid search,
reranking, or metadata filters.

For a low-confidence response the required sentence is exactly: `No specific
policy found — this response is based on general knowledge.` The evaluator does
not draft or send a customer reply.
