# NOAVIA ticket-processing workflow - `workflow.noavia-ticket-pipeline.v1`

> **Current Part 1 delivery:** use [IMPORT_GUIDE.md](IMPORT_GUIDE.md)
> for the direct-OpenAI, native-Qdrant two-workflow implementation. The
> material below is retained as historical reference for the earlier
> classification-service experiment and may describe an old Sheet schema.

This is the reference consumer for the reusable SaaS-factory capability
modules. The repository contains an importable n8n export and an internal
classification service contract. Import/activation and execution in n8n have
not been verified in this repository; see
[`docs/noavia-offline-delivery-evidence.md`](../../docs/noavia-offline-delivery-evidence.md)
before treating the steps below as a release procedure.

## Processing path

`authenticated webhook -> validate/normalize -> optional PDF upload to
Drive + text extraction -> ai.classify-ticket.v1 -> RAG Vector Search ->
route.by-classification.v1 -> Google Sheets append-row -> internal Gmail
notification (only when should_notify)`

RAG retrieval uses n8n's native Qdrant Vector Store node (`load` mode)
directly against `noavia_kb_v1`, with an Embeddings OpenAI subnode for the
query vector - the same collection and provider the ingestion workflow
populates, queried the same way n8n queries it natively rather than via
an HTTP round-trip through classification-service. `classification-
service`'s `/ai/rag-lookup/v1` endpoint still exists and is still tested,
but the main ticket pipeline no longer calls it; only `ai.classify-
ticket.v1` (LLM classification, not a vector-store operation) still goes
through classification-service, since there's no equivalent native n8n
node for a custom structured-output LLM call with this project's schema.

When a ticket has a PDF attachment, `notify.google-drive.v1` uploads it
to a fixed Drive folder (`client_pdfs`) before text extraction runs, using
the filename `{ticket_id}_{requester_email}_{date}.pdf`. The resulting
`webViewLink` is carried through as `drive_link`, written to the Sheet's
`link` column, and included in the notification email body so the owner
can open the original PDF alongside the ticket. A failed or skipped
upload (`onError: continueRegularOutput`) does not block text extraction
or the rest of the pipeline - `link` is simply empty on that row.

Both AI calls use only their published HTTP contracts and pass the same
`X-Correlation-Id`. Validation failures branch before PDF extraction, AI calls,
or delivery and return the shared `{ok:false,error:{code,...}}` envelope with
HTTP 400. A classification error routes to `manual_review`; a RAG error routes
the classified ticket with status `routed_without_rag`. Both are recorded in
the Sheet. Delivery nodes continue into a final outcome check, which returns a
`DELIVERY_ERROR` envelope with HTTP 502 if Sheets or email reports an error.

## Deploy

1. From the repository root, run `docker compose --profile classification-service up -d
 --build`.
2. Import the workflow JSON into n8n.
3. Select a Header Auth credential for ingestion. The tracked export contains
   a Google Sheets credential reference on the storage and disabled
   header-initialization nodes, but the credential's scopes are not
   repository-verifiable. Its Gmail credential reference is intentionally empty;
   bind Gmail only in the isolated n8n workspace after an owner approves a
   controlled, non-production delivery test. Keep the workflow inactive until
   then.
4. The destination tab must have this exact 17-column header row:

   `received_at,ticket_id,correlation_id,requester_email,subject,category,confidence,tags,route_queue,route_email,status,attachment_name,link,rag_match_count,rag_context,error_code,error_message`

   The disabled `Manual Trigger - Initialize Ticket Sheet Header` path emits
   only this header row to the configured test sheet when explicitly enabled
   for initialization; it is not part of ticket processing.

5. Keep the workflow inactive until the owner approves a controlled,
   non-production delivery test. Once approved, the endpoint is
   `POST /webhook/noavia/tickets/v1`.

The AI token comes from n8n's `AI_CLASSIFY_API_KEY` environment value inside
the classify HTTP node. `RAG Vector Search` and `Embeddings OpenAI (RAG)`
use their own bound credentials (`Qdrant account`, `OpenAI account` - same
ones the ingestion workflow uses) instead of that bearer token, since
they're native n8n nodes, not HTTP calls to classification-service. Sheet
values arrive as workflow input. Internal Gmail
routing is server-side only: select the Gmail OAuth2 credential on
`notify.routing-email.v1` (that authorized Gmail identity is the sender) and
set `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` in n8n environment configuration.
For the approved test configuration, map every route-including `default` and
`manual_review`-to the one approved sink recipient. The Gmail node's `sendTo`
value comes only from this allow-list. It has no configurable `from` value, and
ticket request fields cannot set either sender or recipient. Keep the webhook
behind Header Auth.

### Credentials and where they live

Live n8n credential bindings belong in the live n8n instance, NOT in the
repo artifact. The repo artifact (workflow JSON) carries credential ID
references; environment-specific bindings (Gmail OAuth, Header Auth
intake credential) are owner-bound in the isolated n8n instance only.
The choice per credential is documented here so a future operator can
see at a glance what is shared and what is environment-specific.

| Credential             | Node                          | Repo state              | Live state            | Why bucket            |
|------------------------|-------------------------------|-------------------------|-----------------------|-----------------------|
| Ingest Header Auth     | Ingest Support Ticket         | placeholder by design   | owner-bound, secret   | environment-specific  |
|                        |                               | `REPLACE_WITH_...`      | value not in repo     | secret, not shared    |
| Gmail OAuth2           | `notify.routing-email.v1`     | empty by design         | owner-bound live      | environment-specific  |
|                        |                               | (`{id:"",name:""}`)     | in isolated n8n       | OAuth identity, scoped|
| Google Sheets OAuth2   | `notify.google-sheets.v1` +   | real ID reference       | same ID, same scope   | non-secret reference, |
|                        | `initialize.google-sheets-    | (no secret value)       |                       | same in both          |
|                        | header.v1` (disabled)         |                         |                       |                       |
| Google Drive OAuth2    | `notify.google-drive.v1`      | empty by design         | owner-bound live      | environment-specific  |
|                        |                                | (`{id:"",name:""}`)     | in isolated n8n       | OAuth identity, scoped|
| Qdrant account         | `RAG Vector Search`           | real ID reference       | same ID, same scope   | non-secret reference, |
|                        |                                | (no secret value)       |                       | shared with ingestion |
| OpenAI account         | `Embeddings OpenAI (RAG)`     | real ID reference       | same ID, same scope   | non-secret reference, |
|                        |                                | (no secret value)       |                       | shared with ingestion |

Rule: environment-specific secrets (Header Auth, Gmail OAuth) are
owner-bound only; non-secret references (Sheets) live in both. Do not
move secrets into the repo under any circumstances; do not move
non-secret references out of the repo (they are deployment-shared).

## Input contract

JSON and multipart requests use the same fields. For multipart, put the
optional PDF in binary field `data`. Only PDFs are accepted; the documented
limit is 10 MB (enforce the same body limit at the proxy/runtime in production).

```json
{
  "ticket_id": "NVA-1042",
  "subject": "Charged twice",
  "body": "I see two charges for August.",
  "requester_email": "customer@example.com",
  "locale": "en-US",
  "context": { "categories": ["billing", "technical", "account", "feature_request", "complaint", "other"] },
  "config": {
    "sheet_id": "1abc...",
    "sheet_name": "Tickets",
    "top_k": 5,
    "rag_collection": "kb_documents",
    "rag_filter": { "must": [{ "key": "source", "match": { "value": "kb" } }] }
  }
}
```

Required: `subject`, one of `body|message|text`, and one of
`requester_email|from|email`. `requester_name` (or legacy `name`) is
optional: if absent, it is auto-derived from the email local-part
(`alice@example.com` → `alice`). Unknown categories use the server-
configured `default` recipient. Legacy request fields named
`from_email`, `default_route_email`, and `routing_emails` are not
used to derive Gmail sender or recipient addresses.

## Audit telemetry

The workflow emits JSON log records at ingestion, validation rejection, AI
fallback, and delivery failure. Every record uses the reusable schema
`{ts,module,interface_id,version,correlation_id,level,message}`, is appended to
the item's `audit_logs` array, and is written to the n8n process log as one JSON
object. Downstream log shipping can therefore consume records without parsing
free-form execution errors.

## Verify

Run `python3 tests/test_noavia_workflow.py` for credential-free structural
checks. After final credential selection and explicit approval, send one JSON ticket, one multipart ticket with a
small PDF, and temporarily use an invalid AI token to verify the
`manual_review` row and email. Confirm correlation IDs match the Sheet and
service logs.

The webhook responds after processing with an `ok:true` ticket result, a 400
validation envelope, or a 502 delivery envelope. Successful execution payloads
are not saved; failures are retained. Set an explicit execution-retention period
because tickets contain PII. Generic delivery-boundary nodes are named
`route.by-classification.v1`, `notify.google-sheets.v1`, and
`notify.routing-email.v1`, so future products can replace outputs without
modifying either `ai.*` integration.
