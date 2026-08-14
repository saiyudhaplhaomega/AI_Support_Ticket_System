# NOAVIA credential-free RAG evaluation

Run `python3 evals/noavia_rag_eval.py` from the repository root. The 40 labeled
cases cover four variations for each approved knowledge source and eight
unsupported requests. It uses only the deterministic local embedding/store and
writes `evals/noavia_rag_eval_results.json`; it makes no network or model call.

At the measured `0.10` threshold, the current deterministic hybrid baseline
gets Recall@3 `100%`, Top-1 `90.62%`, MRR `95.31%`, and unsupported-fallback
accuracy `100%`, with no false-confidence cases. It combines hash-vector
candidates with a bounded lexical rerank and small fixture-driven term
normalization, so every returned citation has at least two grounded query terms.
This is still a credential- and network-free verification harness, not a live
embedding-model evaluation. The committed result file is generated from the
current fixture and implementation; future retrieval changes must be measured
against the same cases before release use.

For a low-confidence response the required sentence is exactly: `No specific
policy found — this response is based on general knowledge.` The evaluator does
not draft or send a customer reply.
