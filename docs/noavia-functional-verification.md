# NOAVIA functional-verification evidence

## Safe operating mode

`workflow.noavia-ticket-pipeline.v1` (`udAuUv3ca0VPZdI8`) is exported with
`active: false` and was not executed for this release. The portal is explicitly
test-mode only: test mode returns before making an n8n request. Only the
owner-authorized controlled-live mode may use its private server route to
forward to n8n; browser code contains no webhook token, OAuth credential, API
key, recipient, or sender control.

In test mode, the workflow accepts only `NOAVIA Support Tickets - Test`, and
Google Sheets/Gmail credential bindings remain configured-but-unexecuted.
Gmail routes only to the server-side `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` sink;
ticket fields and nested `config` are ignored for routing and cannot set a
sender. No customer-facing draft-email path exists.

When an owner authorizes controlled-live mode, the server allows a webhook URL
only when its origin exactly matches the server-side
`NOAVIA_N8N_INTERNAL_ALLOWED_ORIGIN` (default `http://n8n:5678`). It rejects
URLs with credentials, IP addresses, queries, or fragments, and converts
private-service connection errors into a sanitized 502 response.

Run locally with `docker compose --profile frontend --profile classification-service up --build`.
Open `https://$N8N_PUBLIC_DOMAIN/noavia/`. Do not activate the workflow or
submit a test until an owner approves the controlled side effects.

## Offline matrix

`python3 tests/test_noavia_workflow.py` exercises name/email/subject/body
validation, malformed and empty input, valid/oversized/non-PDF attachments,
empty/scanned-PDF context fallback, all urgency routing, confidence below 0.6,
Qdrant/RAG failure fallback, top-3 citations, exact grounded fallback text,
Sheets mapping, recipient allow-list, sender/recipient injection resistance,
delivery-error logs, and noisy/multi-topic ticket behavior. Model behavior is
mocked; no paid model API is called.

`services/frontend/test_app.py` verifies browser validation, PDF rejection,
test-mode gating, and absence of internal configuration in the page.

## RAG evaluation

The 40-case fixture is `evals/noavia_rag_eval.jsonl`; run
`python3 evals/noavia_rag_eval.py`. It writes the reproducible machine
result to `evals/noavia_rag_eval_results.json` without credentials.

The current deterministic hybrid result is Recall@3 100%, Top-1 90.62%, MRR
0.9531, and unsupported fallback 100%, with no false-confidence cases. The
local path uses bounded hash-vector candidates followed by lexical grounding and
fixture-driven term normalization. The threshold remains 0.10 plus at least two
grounded query terms in the returned source. External embeddings, hosted
reranking services, and production metadata filtering remain unexecuted.
