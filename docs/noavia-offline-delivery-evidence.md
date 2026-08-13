# NOAVIA offline QA delivery evidence

Status: offline evidence only. This record is deliberately separate from deployment or live-integration validation.

## Verified offline evidence

The following checks parse the stored workflow JSON and execute selected Code-node bodies in an isolated local Node.js harness. They do not import, activate, or execute an n8n workflow; they do not contact Google Sheets, email, OpenAI, Qdrant, or any other network service.

Command run on 2026-08-13:

```sh
python3 tests/test_noavia_workflow.py
```

Result:

```text
PASS: 23 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

| Requirement | Offline evidence | Status |
| --- | --- | --- |
| Validation and strict handling | `Validate and Normalize` returns the shared validation envelope for empty required fields, non-PDF attachments, and PDFs over 10 MB; workflow IF branches use strict boolean checks. | Verified |
| Strict service schemas | The existing `services/classification/tests/test_schemas.py` covers blank inputs, RAG `top_k`, and classification confidence bounds. It was not runnable in this checkout because `pytest` is unavailable and packages may not be installed for this task. | Not executed |
| Routing | The harness executes `route.by-classification.v1` for a mapped `billing` category and an unknown category. It verifies the named route, default-recipient fallback, queue, status, and correlation ID propagation. | Verified |
| Confidence override | No confidence-threshold/override configuration or route branch exists in the stored workflow. The current offline test verifies only pass-through of model confidence to the Sheet row. | Gap — not implemented/verified |
| RAG threshold and fallback | `services/classification/tests/test_local_rag.py` contains deterministic threshold and `manual_review` fallback tests for the credential-free reference adapter. This suite was not runnable here because `pytest` is absent. The n8n workflow itself routes an RAG service error to `routed_without_rag`; it has no configured score-threshold decision. | Partial — adapter coverage exists, workflow threshold absent |
| RAG context/citations | The harness verifies scored RAG context is rendered. It also confirms that source metadata is *not* rendered into `rag_context`; therefore source citations are not delivered by the current workflow. | Gap — citations absent |
| Exact Google Sheets columns | The test verifies the 16 ordered columns and one-to-one expressions: `received_at`, `ticket_id`, `correlation_id`, `requester_email`, `subject`, `category`, `confidence`, `tags`, `route_queue`, `route_email`, `status`, `attachment_name`, `rag_match_count`, `rag_context`, `error_code`, `error_message`. | Verified structurally |
| PDF fallback | Invalid/mis-sized attachments are rejected before processing. Empty PDF extraction retains the validated ticket text. | Verified for Code-node behavior |
| Important-step logging | The test verifies required structured fields and JSON process logging for ingestion, validation rejection, classification/RAG fallback, and delivery failure, including correlation IDs. | Verified structurally |

## Untested live integration

No live integration was attempted. In particular, this evidence does **not** prove n8n import/activation/execution, proxy upload enforcement, PDF extractor behavior on a real file, classification/RAG HTTP behavior, OpenAI or Qdrant access, Google Sheets append success or column coercion, SMTP/email delivery, credential permissions, or production log shipping.

The following command was attempted without installing packages, as required:

```sh
(cd services/classification && pytest -q tests/test_local_rag.py tests/test_schemas.py tests/test_api.py tests/test_errors.py tests/test_security.py)
```

Result: `/bin/bash: line 1: pytest: command not found` (exit code 127). No dependency installation was performed.

## Release disposition

Do not represent this delivery as complete end-to-end verification. Before a live release, the workflow owner must implement and test an explicit confidence-override policy, a RAG score-threshold policy, and source citations in the delivered context. A separately authorized integration run must then validate n8n execution and the Sheets/email boundaries with least-privilege test credentials.
