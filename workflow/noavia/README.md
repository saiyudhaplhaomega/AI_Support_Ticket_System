# NOAVIA ticket-processing workflow — `workflow.noavia-ticket-pipeline.v1`

This is the reference consumer for the reusable SaaS-factory capability
modules. The repository contains an importable n8n export and an internal
classification service contract. Import/activation and execution in n8n have
not been verified in this repository; see
[`docs/noavia-offline-delivery-evidence.md`](../../docs/noavia-offline-delivery-evidence.md)
before treating the steps below as a release procedure.

## Processing path

`authenticated webhook -> validate/normalize -> optional PDF extraction ->
ai.classify-ticket.v1 -> ai.rag-lookup.v1 -> route.by-classification.v1 ->
Google Sheets -> routing email`

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
3. Replace each `REPLACE_WITH_N8N_CREDENTIAL_ID` by selecting a Header Auth
   credential for ingestion, a least-privilege Google Sheets OAuth2
   credential, and an SMTP credential.
4. Create the destination tab with this exact header row:

   `received_at,ticket_id,correlation_id,requester_email,subject,category,confidence,tags,route_queue,route_email,status,attachment_name,rag_match_count,rag_context,error_code,error_message`

5. Activate the workflow. The endpoint is `POST /webhook/noavia/tickets/v1`.

The AI token comes from n8n's `AI_CLASSIFY_API_KEY` environment value inside
the two HTTP nodes. Product-specific Sheet/routing values arrive as trusted
workflow input, as required by the architecture. Keep the webhook behind
Header Auth; callers can otherwise choose notification recipients.

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
    "from_email": "support@example.com",
    "default_route_email": "support@example.com",
    "routing_emails": {
      "billing": "billing@example.com",
      "technical": "engineering@example.com",
      "manual_review": "support-lead@example.com"
    },
    "top_k": 5,
    "rag_collection": "kb_documents",
    "rag_filter": { "must": [{ "key": "source", "match": { "value": "kb" } }] }
  }
}
```

Required: `subject`, one of `body|message|text`, one of
`requester_email|from|email`, and `sheet_id`, `sheet_name`, `from_email`, and
`default_route_email` under `config`. Unknown categories use the default route.

## Audit telemetry

The workflow emits JSON log records at ingestion, validation rejection, AI
fallback, and delivery failure. Every record uses the reusable schema
`{ts,module,interface_id,version,correlation_id,level,message}`, is appended to
the item's `audit_logs` array, and is written to the n8n process log as one JSON
object. Downstream log shipping can therefore consume records without parsing
free-form execution errors.

## Verify

Run `python3 tests/test_noavia_workflow.py` for credential-free structural
checks. After deployment, send one JSON ticket, one multipart ticket with a
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
