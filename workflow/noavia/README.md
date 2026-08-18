# NOAVIA Part 1 n8n workflows

This folder contains the current interview submission workflows:

- `workflow.noavia-kb-ingestion.v1.json` - manual KB ingestion: Markdown
  files → 800-character recursive chunks (120 overlap) → OpenAI
  `text-embedding-3-small` (1536) → Qdrant `noavia_kb_v1`.
- `workflow.noavia-ticket-pipeline.v2.1.json` - webhook ticket processing:
  required validation → optional PDF enrichment → OpenAI structured
  classification → top-3 native Qdrant retrieval → OpenAI grounded draft →
  urgency/confidence routing → Google Sheets/internal notification.

- `workflow.noavia-source-store-bootstrap.v1.json` - one-time creation of the
  persistent editable `noavia_source_documents_v2` table.
- `workflow.noavia-document-manager.v1.json` - authenticated create, replace,
  and delete workflow for ticket, public, and admin source documents.
- `workflow.noavia-source-library.v1.json` - protected canonical source-text
  listing and reading for the administrator UI.
- `workflow.noavia-kb-webhook-update.v1.json` - legacy ticket-only upload
  compatibility workflow; use the document manager for new work.
- `workflow.noavia-public-chat.v1.json` - isolated public-company RAG chat.
- `workflow.noavia-admin-chat.v1.json` - isolated private admin RAG chat.

Start with [IMPORT_GUIDE.md](IMPORT_GUIDE.md). It names the
exact import order, credential bindings, test-sheet header, safe notification
configuration, and verification commands.

## Required behavior

- Name, valid email, subject, and non-empty message are required.
- A PDF is optional; extraction failure is logged and does not stop processing.
- Classification requires `category`, `urgency`, `sentiment`, `confidence`,
  and `summary`; invalid model output enters manual review.
- Retrieval uses at most three chunks. If none satisfy the threshold, the
  draft includes: `No specific policy found - this response is based on
  general knowledge.`
- The generated customer response is saved as a draft only. It is never sent
  to the requester.
- Critical/high send a full internal email; medium sends a brief internal
  email; low writes only to the Sheet. Confidence below 0.6 always sets
  `needs-manual-review` and sends a full internal email.

The previous classification-service/MiniMax guide is preserved in
[README.legacy-classification-service.md](README.legacy-classification-service.md)
for historical reference only; do not use it to deploy this Part 1 version.
