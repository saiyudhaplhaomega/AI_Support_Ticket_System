# NOAVIA isolated readiness evidence

Status: partially live-validated, with delivery integrations configured but
deliberately unexecuted. This is a control-plane and local-fixture record, not
a claim that Google Sheets, Gmail, OpenAI, or production Qdrant ingestion was
tested.

Repository baseline verification: `origin/main` resolved to
`e8ef9bd2daacf08a0fcbf412be036988ae78df1a` on 2026-08-14. This is a recorded
baseline SHA, not an instruction to push or activate anything.

## Isolated n8n workspace — 2026-08-14

The dedicated `paperclip-noavia` API capability was used only against the
internal n8n endpoint. Workflow discovery returned exactly one workflow:

| Field | Observed value |
| --- | --- |
| ID | `udAuUv3ca0VPZdI8` |
| Name | `workflow.noavia-ticket-pipeline.v1` |
| Nodes | 26 |
| Activation state | inactive |
| Webhook path | `noavia/tickets/v1` |

The imported workflow has the same node names and executable node
configuration as `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`.
n8n assigned its own `webhookId`; its empty `pinData` representation differs
from the export, which is non-executable metadata.

On 2026-08-14, the owner manually selected the Gmail OAuth2 credential on
`notify.routing-email.v1` and saved the workflow inactive. The repository
artifact retains the Google Sheets OAuth2 binding on both
`notify.google-sheets.v1` and the disabled
`initialize.google-sheets-header.v1`. Its append-row mapping is structurally
verified as the exact 16-column schema:

`received_at,ticket_id,correlation_id,requester_email,subject,category,confidence,tags,route_queue,route_email,status,attachment_name,rag_match_count,rag_context,error_code,error_message`

Google Sheets and Gmail bindings are configured but have not been executed.
No side-effecting live test has occurred: a live run could write a Sheet row
or send email, so these bindings remain owner-confirmed rather than
execution-verified.

### Gmail destination control

`notify.routing-email.v1` is an n8n Gmail node, not an SMTP node. Its sender is
the selected Gmail OAuth2 identity; there is no sender-address expression in
the workflow. Its `sendTo` expression reads only `route.email`, which is built
from the server-side `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` environment value.
Ticket fields—including `requester_email`, `from_email`, `default_route_email`,
and `routing_emails`—must never supply the Gmail sender or recipient.

For the approved offline/test configuration, every configured route must point
to the single approved test/sink recipient (including `default` and
`manual_review`). A missing or invalid allow-list entry produces no route email
and must be corrected before any owner-approved execution. This rule is
structurally tested only; Gmail has not been executed.

## Qdrant / knowledge-base — live ingestion 2026-08-14

Qdrant confirmed reachable at `http://qdrant:6333` (unauthenticated,
`AI_QDRANT_AUTH_ENABLED=false` per owner approval). Collection `noavia_kb_v1`
created with 256-dimensional cosine vectors using `DeterministicHashEmbedder`
(credential-free; production upgrade path is to swap in the OpenAI adapter).

All eight fictional Markdown sources ingested directly via Qdrant REST API:

| # | File | Chunks |
|---|------|--------|
| 1 | api-token-rotation.md | 1 |
| 2 | csv-import.md | 1 |
| 3 | data-retention.md | 1 |
| 4 | duplicate-charge.md | 1 |
| 5 | email-notifications.md | 1 |
| 6 | knowledge-search.md | 1 |
| 7 | password-reset.md | 1 |
| 8 | priority-and-sla.md | 1 |

**Total: 8 points confirmed in collection.**

**Duplicate-charge top-3 retrieval:**
1. `knowledge-base/noavia/duplicate-charge.md#0` (score=0.255)
2. `knowledge-base/noavia/csv-import.md#0` (score=0.056)
3. `knowledge-base/noavia/knowledge-search.md#0` (score=0.055)
— low_confidence=False (duplicate-charge correctly ranked first)

**Password-reset citation:**
- source=`knowledge-base/noavia/password-reset.md` score=0.424 (top match)

**Low-confidence / astronomy (unrelated) query:**
- Top match score=0.143 (above threshold=0.10); retrieval returns results but
  confidence is marginal. Production threshold can be tuned after live
  OpenAI embeddings improve separation.

## Tests executed

```text
python3 tests/test_noavia_workflow.py
PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present

./scripts/verify-baseline.sh
PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

## Remaining owner / platform actions

1. **OpenAI upgrade** (optional for production): Replace `DeterministicHashEmbedder`
   with OpenAI `text-embedding-3-small` by injecting `OPENAI_API_KEY` into
   the classification service only (do not inject it into n8n). Re-ingest `knowledge-base/noavia` via the service
   to get production-quality embeddings. The collection name `noavia_kb_v1` and
   point count remain the same.
2. **n8n credentials**: The Sheets and Gmail OAuth2 bindings are selected in
   the isolated workflow; before a live test, an owner must confirm the Header
   Auth intake credential and that the selected Google identities retain only
   the intended test spreadsheet/tab and approved sender access. Supply
   `config.rag_collection = noavia_kb_v1`.
3. **Live integration test** (owner approval required): With explicit approval
   for side effects, activate and test using a non-production Sheet and the
   approved Gmail test/sink recipient, then deactivate immediately after.

No credential value is included in this record.
