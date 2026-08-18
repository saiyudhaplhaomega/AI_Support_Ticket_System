# NOAVIA documentation audit - changes required

Audit date: 2026-08-14. Result: **not accepted**.

Evidence checked: the tracked workflow export, Git history, current GitHub
`origin/main`, and credential-free repository checks. This audit is dated
2026-08-14 evidence, not a statement of the present remote or release state.
The export inspected for the audit contains 26 nodes. The recorded checks
passed: workflow/baseline (26 nodes), RAG fixture, classification suite (39
tests), and frontend suite (4 tests). No tracked live-secret pattern was found.

## Required corrections

1. Update `docs/noavia-rag-evaluation.md` from the retired hash baseline.
   The current committed result at threshold `0.10` is Recall@3 `1.0000`,
   Top-1 `0.9062`, MRR `0.9531`, unsupported fallback `1.0000`, and no
   false-confidence cases. Deterministic local hybrid retrieval is implemented;
   it remains credential- and network-free, not a live model evaluation.
   (Corrected 2026-08-14: `evals/noavia_rag_eval.py`'s distribution helper used
   a naive middle-index instead of a true median, which made a *reproduction*
   run report the wrong `supported_top_score_distribution.median`, 0.226805
   instead of the committed 0.225769. The metric above, MRR, was never
   affected. The script now uses `statistics.median`; a fresh run matches the
   committed `evals/noavia_rag_eval_results.json` exactly.)
2. Make the equivalent correction in `docs/noavia-functional-verification.md`.
   It must not say hybrid retrieval was not added. Qualify its portal forwarding
   statement: test mode returns before any n8n request; forwarding is
   controlled-live-only.
3. Correct `workflow/noavia/README.md`: the tracked export has an empty Gmail
   credential reference, so it must not say a Gmail OAuth2 credential is
   selected. A Sheets credential reference is present, but least-privilege
   scope is not repository-verifiable.
4. Remove or archive stale release assertions. Keep recovery and test
   provenance dated, and do not call local-ahead commits published. Offline
   evidence must not imply remote-branch equality or a completed release
   handoff.
5. Use status labels consistently: structural/Code-node and local RAG checks
   are **Verified offline**; Sheets/Gmail bindings are **Configured but
   unexecuted** (Gmail only in the isolated environment, not this export); n8n
   activation/execution, live Sheets/Gmail, OpenAI/MiniMax, and production
   Qdrant ingestion are **Planned/unverified**.
6. Trim the README to safe commands and canonical links. It duplicates
   infrastructure/provider/security detail already owned by the architecture
   and classification-service documents.

The no-SMTP statement is correct: the export uses an n8n Gmail node, not SMTP.
