# knowledge-base/noavia/

The RAG corpus for the ticket pipeline. Fictional but realistic support documentation.

Indexed into the Qdrant collection `noavia_kb_v1` by
`workflow.noavia-kb-ingestion.v1.json`, which mounts this folder read-only at
`/files/noavia`.

| Document | Topic |
|---|---|
| `password-reset.md` | Account recovery and login failures |
| `duplicate-charge.md` | Billing disputes and duplicate payments |
| `data-retention.md` | Retention and deletion policy |
| `api-token-rotation.md` | API credential lifecycle |
| `csv-import.md` | Historical ticket import |
| `email-notifications.md` | Notification settings |
| `knowledge-search.md` | Search behaviour |
| `priority-and-sla.md` | Urgency levels and response targets |
| `live-kb-verification.md` | Verification fixture used during live testing |

Nine documents, inside the 5 to 10 the task specifies.

## Chunking

800 characters with 120 overlap, recursive splitter with markdown separators, so splits
prefer heading and paragraph boundaries. 800 keeps a complete policy statement intact
while leaving room for three chunks plus the ticket in the draft prompt. The 15 percent
overlap prevents a policy sentence that straddles a boundary from being lost to both
neighbours.

## Adding a document

Drop the markdown file here, then re-run the ingestion workflow. Ingestion **inserts
rather than upserts**, so delete the `noavia_kb_v1` collection first or you will get
duplicate chunks.

The filename becomes the `source` metadata value, which is what appears as a citation
in the draft reply. Name files accordingly.
