# NOAVIA offline QA delivery evidence

Status: offline evidence only. This record is deliberately separate from deployment or live-integration validation.

## Verified offline evidence

The following checks parse the stored workflow JSON and execute selected Code-node bodies in an isolated local Node.js harness. They do not import, activate, or execute an n8n workflow; they do not contact Google Sheets, email, OpenAI, Qdrant, or any other network service.

Commands run on 2026-08-14:

```sh
python3 tests/test_noavia_workflow.py
```

Result:

```text
PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

| Requirement | Offline evidence | Status |
| --- | --- | --- |
| Validation and strict handling | `Validate and Normalize` returns the shared validation envelope for empty required fields, non-PDF attachments, and PDFs over 10 MB; workflow IF branches use strict boolean checks. | Verified |
| Strict service schemas and service contracts | `python3 -m pytest -q` in `services/classification/` ran all 38 offline tests, including schemas, API envelopes, error handling, local RAG, Qdrant credential forwarding, and security checks. | Verified offline |
| Routing | The harness executes `route.by-classification.v1` for a mapped `billing` category and the default-recipient fallback. It verifies queue, status, and correlation-ID propagation. | Verified |
| Confidence override | The workflow routes classification confidence below `0.6` to the `manual_review` queue with `needs-manual-review` status, regardless of urgency. The harness exercises confidence `0.44` and `0.59`, including critical urgency. | Verified offline |
| RAG threshold and fallback | The workflow validates `config.rag_min_score` in `[0, 1]`, defaulting to `0.6`, and filters retrieval matches at that threshold. The harness supplies a `0.59` match and verifies no retained matches/citations plus the exact fallback sentence: `No specific policy found — this response is based on general knowledge.` RAG HTTP-error handling still records `routed_without_rag` unless the item is already marked for manual review. | Verified offline |
| Grounded draft and citations | `draft.grounded-reply.v1` receives retained knowledge-source metadata and emits citation objects plus numbered source citations in `grounded_draft_reply.text`. The harness verifies source metadata and `[1] kb/duplicate-charge`. The Sheet's `rag_context` remains scored content rather than a citation field. | Verified offline |
| Exact Google Sheets columns | The test verifies the 16 ordered columns and one-to-one expressions: `received_at`, `ticket_id`, `correlation_id`, `requester_email`, `subject`, `category`, `confidence`, `tags`, `route_queue`, `route_email`, `status`, `attachment_name`, `rag_match_count`, `rag_context`, `error_code`, `error_message`. | Verified structurally |
| PDF fallback | Invalid/mis-sized attachments are rejected before processing. Empty PDF extraction retains the validated ticket text. | Verified for Code-node behavior |
| Important-step logging | The test verifies required structured fields and JSON process logging for ingestion, validation rejection, classification/RAG fallback, and delivery failure, including correlation IDs. | Verified structurally |

## Release verification

The current release handoff records the exact published SHA after `git fetch
origin main` and an equality check between local `HEAD` and `origin/main`.
This QA record deliberately avoids pinning a stale release SHA. On 2026-08-14,
the credential-free workflow harness, `./scripts/verify-baseline.sh`, and the
38-test classification suite all passed. The workflow export uses only
environment-variable and credential references; no literal credential value is
recorded in this evidence. This is offline verification, not a live
operational test.

## Explicitly unverified live integrations and deployment behavior

No live integration was attempted. In particular, this evidence does **not** prove:

- n8n import, activation, or execution;
- webhook/proxy Header Auth or body-limit enforcement;
- PDF extraction from a real file;
- classification/RAG HTTP behavior or OpenAI/Qdrant access;
- Google Sheets writes, schema coercion, OAuth least privilege, or Gmail delivery/sender permissions;
- credential permissions or secret-store injection;
- container, network, HTTPS, or deployment behavior; or
- production log shipping or execution-retention behavior.

The following command completed using the already available test environment:

```sh
(cd services/classification && python3 -m pytest -q)
```

Result: `38 passed`. No package installation, paid model call, workflow
activation, or external delivery was performed.

## Delivery checklist

- [x] Canonical workflow export and credential-free offline harness are present.
- [x] Offline structural/Code-node evidence passes for validation, logging, confidence override, RAG threshold/fallback, citations, routing, and delivery contracts.
- [x] Published-release SHA equality and offline verification recorded in the final handoff.
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
