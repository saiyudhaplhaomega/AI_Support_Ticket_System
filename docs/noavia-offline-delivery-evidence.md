# NOAVIA offline QA delivery evidence

Status: offline evidence only. This record is deliberately separate from deployment or live-integration validation.

## Verified offline evidence

The following checks parse the stored workflow JSON and execute selected Code-node bodies in an isolated local Node.js harness. They do not import, activate, or execute an n8n workflow; they do not contact Google Sheets, email, OpenAI, Qdrant, or any other network service.

Primary command run on 2026-08-13:

```sh
python3 tests/test_noavia_workflow.py
```

Result:

```text
PASS: 24 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

| Requirement | Offline evidence | Status |
| --- | --- | --- |
| Validation and strict handling | `Validate and Normalize` returns the shared validation envelope for empty required fields, non-PDF attachments, and PDFs over 10 MB; workflow IF branches use strict boolean checks. | Verified |
| Strict service schemas | The existing `services/classification/tests/test_schemas.py` covers blank inputs, RAG `top_k`, and classification confidence bounds. It was not runnable in this checkout because `pytest` is unavailable and packages may not be installed for this task. | Not executed |
| Routing | The harness executes `route.by-classification.v1` for a mapped `billing` category and the default-recipient fallback. It verifies queue, status, and correlation-ID propagation. | Verified |
| Confidence override | Published commit `8a4df5f` routes classification confidence below `0.6` to the `manual_review` queue with `needs-manual-review` status, regardless of urgency. The harness exercises confidence `0.44` and `0.59`, including critical urgency. | Verified offline |
| RAG threshold and fallback | The workflow validates `config.rag_min_score` in `[0, 1]`, defaulting to `0.6`, and filters retrieval matches at that threshold. The harness supplies a `0.59` match and verifies no retained matches/citations plus the exact fallback sentence: `No specific policy found — this response is based on general knowledge.` RAG HTTP-error handling still records `routed_without_rag` unless the item is already marked for manual review. | Verified offline |
| Grounded draft and citations | `draft.grounded-reply.v1` receives retained knowledge-source metadata and emits citation objects plus numbered source citations in `grounded_draft_reply.text`. The harness verifies source metadata and `[1] kb/duplicate-charge`. The Sheet's `rag_context` remains scored content rather than a citation field. | Verified offline |
| Exact Google Sheets columns | The test verifies the 16 ordered columns and one-to-one expressions: `received_at`, `ticket_id`, `correlation_id`, `requester_email`, `subject`, `category`, `confidence`, `tags`, `route_queue`, `route_email`, `status`, `attachment_name`, `rag_match_count`, `rag_context`, `error_code`, `error_message`. | Verified structurally |
| PDF fallback | Invalid/mis-sized attachments are rejected before processing. Empty PDF extraction retains the validated ticket text. | Verified for Code-node behavior |
| Important-step logging | The test verifies required structured fields and JSON process logging for ingestion, validation rejection, classification/RAG fallback, and delivery failure, including correlation IDs. | Verified structurally |

## Independent verification

SAI-24 independently verified published commit `8a4df5f9aad87da63e4ebd1c6a1dc50902c517c9` on 2026-08-13. It reported that local `HEAD` and `origin/main` resolved to that SHA, the worktree was clean, `python3 tests/test_noavia_workflow.py` passed with the result above, and `git diff --check 8a4df5f^ 8a4df5f` passed. Its review also found no literal secret material in the patch; the workflow uses environment-variable and credential references only. This is independent offline evidence, not a live operational test.

## Explicitly unverified live integrations and deployment behavior

No live integration was attempted. In particular, this evidence does **not** prove:

- n8n import, activation, or execution;
- webhook/proxy Header Auth or body-limit enforcement;
- PDF extraction from a real file;
- classification/RAG HTTP behavior or OpenAI/Qdrant access;
- Google Sheets writes, schema coercion, OAuth least privilege, or SMTP delivery/from-address permissions;
- credential permissions or secret-store injection;
- container, network, HTTPS, or deployment behavior; or
- production log shipping or execution-retention behavior.

The following command was attempted without installing packages, as required:

```sh
(cd services/classification && pytest -q tests/test_local_rag.py tests/test_schemas.py tests/test_api.py tests/test_errors.py tests/test_security.py)
```

Result: `/bin/bash: line 1: pytest: command not found` (exit code 127). No dependency installation was performed.

## Delivery checklist

- [x] Canonical workflow export and credential-free offline harness are present.
- [x] Offline structural/Code-node evidence passes for validation, logging, confidence override, RAG threshold/fallback, citations, routing, and delivery contracts.
- [x] Published commit and independent SAI-24 offline verification recorded.
- [ ] Import and activate the workflow in an approved non-production n8n environment.
- [ ] Validate all live-integration items above with least-privilege test credentials and an approved test ticket.
- [ ] Set and verify production PII/log retention before release.

## Release disposition

Do not represent this delivery as complete end-to-end verification. The three previous offline workflow gaps are implemented and independently verified, but a separately authorized integration run must validate n8n execution and every live boundary listed above with least-privilege test credentials.

## Provider split limitation (SAI-32)

Static verification covers the exported workflow and provider configuration.
No n8n workflow was activated and no Google Sheets or email node was executed.
Live MiniMax/OpenAI calls remain deliberately unverified because this repository
contains no credentials; service tests use mocks when the Python test runner is
available.
