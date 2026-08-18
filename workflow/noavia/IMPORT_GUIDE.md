# Import guide - current NOAVIA Part 1 exports

Run every command from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.

This guide is authoritative for the four current exports. The old
classification-service experiment is preserved only as
`README.legacy-classification-service.md`; do not use it for this interview
delivery.

## 1. Build and inspect the exports

Run:

```powershell
python scripts/build_workflow.py
python scripts/verify_workflows.py
```

Expected result: `PASS: ticket=...` with ticket, ingestion, and KB-update graphs.
The build step generates the ticket export; the verifier ensures direct OpenAI
classification and drafting, native Qdrant RAG, routing, the required fallback
text, and the Sheet fields are present.

## 2. Import KB ingestion first

In n8n choose **Create workflow → Import from File** and select
`workflow/noavia/workflow.noavia-kb-ingestion.v1.json`. Bind the existing
OpenAI and Qdrant credentials. Its source directory is `/files/noavia/*.md`,
so run the local stack with `docker compose up -d` first. Execute the Manual
Trigger.

Success means Qdrant collection `noavia_kb_v1` contains chunks created with
`text-embedding-3-small` at 1536 dimensions. The workflow uses an 800-character
recursive Markdown splitter with a 120-character overlap and writes source
metadata for every chunk.

## 3. Import the ticket workflow

Import `workflow/noavia/workflow.noavia-ticket-pipeline.v2.1.json`. Bind Header
Auth, OpenAI, Qdrant, Google Drive, Google Sheets, and Gmail credentials. The
workflow uses OpenAI `gpt-4o-mini` for both structured classification and the
stored draft response; it never sends that draft to the requester.

Before activating, update row 1 of the supplied test sheet (the existing
`Sheet1` tab) to this exact header row. This is an in-place header update only;
leave all existing ticket rows below it intact:

`ticket_id,timestamp,name,email,subject,category,urgency,sentiment,confidence,ai_summary,draft_response,knowledge_sources,status,processing_log,attachment_present,attachment_filename,attachment_drive_link,attachment_extraction_status,invoice_check`

Then open **notify.google-sheets.v1** and click the field-refresh control once
so n8n reads those 19 headers. `attachment_drive_link` is the shareable Google
Drive URL for an uploaded PDF. `invoice_check` is a readable assessment of a
PDF attachment: the structured classifier decides first, with a logged keyword
fallback only if that decision is unavailable. It is not an antivirus result.
Map all recipients in
`NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` to a single controlled test inbox. Run
the safe paths in [../../docs/build/02_SAFE_N8N_TESTS.md](../../docs/build/02_SAFE_N8N_TESTS.md).

Why this order: indexing first prevents an empty collection from making every
draft take the low-similarity fallback.

## 4. Import the source store and document manager

Import `workflow/noavia/workflow.noavia-source-store-bootstrap.v1.json` and
run its **Manual Trigger once**. It creates the persistent n8n Data Table
`noavia_source_documents_v2`, which is the editable source of truth. It is
safe to run again because the table creation is idempotent.

If a previous draft created `noavia_source_documents_v1`, leave it untouched.
This versioned table deliberately avoids altering or deleting earlier records.
Re-upload the small set of approved sources through the administrator UI to
place them in v2 with retirement support.

Then import `workflow/noavia/workflow.noavia-document-manager.v1.json` and
`workflow/noavia/workflow.noavia-source-library.v1.json`. Bind the same Header
Auth, OpenAI, and Qdrant credentials as the ticket workflow. The document
manager accepts upserts and deletes at `/webhook/noavia/documents/v1`; the
source library reads canonical document text at
`/webhook/noavia/source-library/v1`.

Set `NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL` and
`NOAVIA_N8N_SOURCE_LIBRARY_WEBHOOK_URL` in the frontend runtime. The Google-
authenticated browser can upload, view, edit, replace, and delete source
documents in the ticket, public, and admin areas. The manager inserts a new
vector version first, saves canonical source text, then removes the older
vector version. A failed source save leaves the old vectors in place; a failed
cleanup leaves both vector versions rather than losing content, and can be
retried safely. Deletion retires the canonical source rather than erasing it,
so a failed final update remains recoverable. Never expose n8n Header Auth or
call these webhooks directly from a browser.

## 5. Import the isolated public chatbot

Import `workflow/noavia/workflow.noavia-public-chat.v1.json`. Bind its own
Header Auth credential (do not reuse the ticket or KB-update credential), the
existing OpenAI embedding credential, the Qdrant credential, and your existing
tested **MiniMax account** credential. The workflow uses n8n's native MiniMax
Chat Model through a Basic LLM Chain, not an HTTP Request node. Activate it only after
`noavia_public_chat_kb_v1` has been populated with approved public company documents.

Set `NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL` to the exact HTTPS endpoint ending in
`/webhook/noavia/public-chat/v1`, and set the matching separate
`NOAVIA_N8N_PUBLIC_CHAT_HEADER_NAME` and `NOAVIA_N8N_PUBLIC_CHAT_HEADER_VALUE`
only in the frontend runtime. The public frontend page is `/chat`. It limits
requests, sends only the question to n8n, retrieves only from the hardcoded
public collection, and returns source references. It must never use
`noavia_kb_v1` or any private admin collection.

## 6. Import the protected document library and private assistant

The source-library workflow from step 4 is the canonical list/read endpoint;
it reads source text from n8n Data Tables, never reconstructed vector chunks.
The frontend routes deletes through the document manager, so a delete removes
both the canonical source and all matching Qdrant vectors.

Import `workflow/noavia/workflow.noavia-admin-chat.v1.json`, bind its own
Header Auth, Qdrant, OpenAI embedding, and the same MiniMax account credential,
then set the matching `NOAVIA_N8N_ADMIN_CHAT_*` frontend variables. Its retrieval collection
is hardcoded to `noavia_admin_kb_v1`. It returns an answer and up to three
source filenames. Activate it only after a controlled citation-bearing answer
has been verified.
