# NOAVIA isolated readiness evidence

Status: partially live-validated, with external integrations deliberately
unconfigured. This is a control-plane and local-fixture record, not a claim
that Google Sheets, SMTP, OpenAI, or production Qdrant ingestion was tested.

## Isolated n8n workspace — 2026-08-14

The dedicated `paperclip-noavia` API capability was used only against the
internal n8n endpoint. Workflow discovery returned exactly one workflow:

| Field | Observed value |
| --- | --- |
| ID | `udAuUv3ca0VPZdI8` |
| Name | `workflow.noavia-ticket-pipeline.v1` |
| Nodes | 24 |
| Activation state | inactive |
| Webhook path | `noavia/tickets/v1` |

The imported workflow has the same node names and executable node
configuration as `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`.
n8n assigned its own `webhookId`; its empty `pinData` representation differs
from the export, which is non-executable metadata. No activation or execution
was attempted: the three delivery credentials remain placeholders and a live
run could write a Sheet row or send email.

## Qdrant / knowledge-base boundary

The internal Qdrant health endpoint returned `200`; its collection listing was
empty. The classification service DNS name was not available from this
execution environment, and the required scoped service credentials were not
present. Therefore no Qdrant collection was created and no direct unauthenticated
write was attempted. Direct writes would bypass the documented
`classification-service` collection-scoped JWT boundary.

The approved local fixture path was nevertheless exercised against all eight
fictional Markdown sources. It ingested eight deterministic chunks, retained
source metadata, and returned this duplicate-charge top three:

1. `knowledge-base/noavia/duplicate-charge.md#0` (0.265)
2. `knowledge-base/noavia/priority-and-sla.md#0` (0.190)
3. `knowledge-base/noavia/knowledge-search.md#0` (0.095)

The first citation source was
`knowledge-base/noavia/duplicate-charge.md`; an unrelated astronomy query
returned `low_confidence=true` with fallback `manual_review`.

## Tests executed

```text
python3 tests/test_noavia_workflow.py
PASS: 24 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present

./scripts/verify-baseline.sh
PASS: 24 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

## Required owner / platform action

1. Start the internal `classification-service` profile and inject
   `OPENAI_API_KEY`, `AI_CLASSIFY_API_KEY`, and a collection-scoped
   `AI_QDRANT_API_KEY` for a newly approved NOAVIA-only collection (for
   example `noavia_kb_v1`). The Qdrant signing/admin secret stays in Qdrant.
2. Through that service, ingest the eight files in `knowledge-base/noavia`,
   then record collection/chunk counts and live top-three retrieval evidence.
3. In n8n, replace the three credential placeholders with: Header Auth for
   webhook intake, least-privilege Google Sheets OAuth2 access to the intended
   test spreadsheet/tab, and SMTP access restricted to the approved sender.
   Supply the ticket's `config.rag_collection` as the approved collection name.
4. With explicit approval for side effects, perform the final activated test
   using a non-production Sheet and SMTP sink, then deactivate if it is not a
   production release.

No credential value is included in this record.
