# NOAVIA Part 1 - current implementation

This is the current interview-delivery architecture. Run commands from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.

## Architecture decisions

The reproducible local stack contains n8n, Qdrant, and the optional frontend.
`compose.yaml` starts them with `docker compose up -d`; n8n is at
`http://localhost:5678`, the frontend is at `http://localhost:8081`, and the
Qdrant dashboard is at `http://localhost:6333/dashboard`.

Two native n8n workflows implement Part 1:

1. `workflow/noavia/workflow.noavia-kb-ingestion.v1.json` loads the NOAVIA
   Markdown knowledge base, splits it into 800-character chunks with 120
   overlap, embeds with `text-embedding-3-small` (1536 dimensions), and adds
   documents to the `noavia_kb_v1` Qdrant collection.
2. `workflow/noavia/workflow.noavia-ticket-pipeline.v2.1.json` validates the
   webhook ticket (including required name), optionally extracts PDF text,
   classifies it through OpenAI with strict JSON validation, retrieves three
   matching chunks through the native Qdrant node, and asks OpenAI for a
   grounded **draft**. The draft is never sent to the customer.

The document-management batch adds a persistent n8n Data Table for canonical
Markdown/text sources, a guarded upsert/delete workflow, and a source-library
read workflow. It keeps ticket, public-chat, and admin-assistant documents in
separate Qdrant collections. Qdrant remains a derived index: source text is
read and edited from the Data Table, never reconstructed from chunks.

The retrieval node uses the same embedding model as ingestion and a similarity
threshold. When no chunk passes it, the draft prompt includes exactly:

`No specific policy found — this response is based on general knowledge.`

Routing is explicit: critical/high writes Google Sheets and emails the full
internal case; medium writes Sheets and sends a brief internal notification;
low writes Sheets only. A classifier confidence below 0.6 is marked
`needs-manual-review` regardless of urgency. The Sheet row records ticket
details, classification, draft, sources, processing log, attachment status,
and invoice-check result.

## Verification

Run:

```powershell
python scripts/build_workflow.py
python tests/test_noavia_workflow.py
python scripts/verify_workflows.py
```

Success is five passing workflow tests followed by a `PASS:` verification
line. The backend and frontend suites are also covered by the build order.

## Import and live validation

Follow [the workflow import guide](../workflow/noavia/IMPORT_GUIDE.md)
to import both exports inactive, bind credentials, ingest the KB, and perform
a controlled test. Live validation intentionally requires owner approval
because it can write the supplied Google Sheet, consume OpenAI credits, and
send internal mail.

The older retired-platform and superseded Part 1 documents, and the
`learning/` material is kept as historical context for the previous
classification-service experiment; do not use it to configure this submission.
