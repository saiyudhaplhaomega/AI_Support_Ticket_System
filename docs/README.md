# docs/

Design notes and reference material.

## Start here

| I want to... | Read |
|---|---|
| Install and run the system | [root `README.md`](../README.md) |
| Understand why it is built this way | [`design-rationale.md`](design-rationale.md) |
| Understand what every node does | [`workflow-walkthrough.md`](workflow-walkthrough.md) |
| Import the workflows into n8n | [`../workflow/noavia/IMPORT_GUIDE.md`](../workflow/noavia/IMPORT_GUIDE.md) |

## Reference

| Document | Subject |
|---|---|
| `design-rationale.md` | Architecture decisions, AI output validation, RAG design, and what to improve next |
| `workflow-walkthrough.md` | Node-by-node reference for the ticket pipeline and knowledge ingestion |
| `decisions.md` | Architecture decision record, including superseded decisions |
| `architecture-and-data-flow.md` | How data moves through the system |
| `code-tour.md` | Guided tour of the repository |
| `rag-evaluation.md` | Retrieval evaluation method and results |
| `08_APPLICATION_FEATURES.md` | Feature inventory across all workflows |

## Build and test notes

| Document | Subject |
|---|---|
| `build/02_SAFE_N8N_TESTS.md` | Running tests without touching live external services |
| `build/03_LIVE_KB_VERIFICATION.md` | Verifying the knowledge base against a live Qdrant |
| `build/04_VERCEL_GOOGLE_ADMIN.md` | Frontend hosting and Google admin setup |
| `testing-guide.md` | Testing approach |
| `how-to-view-and-test.md` | Manual verification walkthrough |

## Status and checklists

| Document | Subject |
|---|---|
| `current-architecture.md` | Current architecture summary |
| `delivery-checklist.md` | Delivery checklist |
| `delivery-status.md` | Status summary |

## Navigation

`00_START_HERE.md`, `01_BUILD_ORDER.md`, `99_DOC_ORDER.md` and `getting-started.md` are
earlier entry points, kept because they still describe the build order. For setup, the
root README is more current.

## One thing that dates a document

The system originally ran ticket classification behind a FastAPI microservice, and used
MiniMax for classification and drafting. Both changed: classification and drafting now
run on native n8n OpenAI nodes, and the microservice under `services/classification/` is
retired.

If a document describes the ticket workflow calling a classification service over HTTP,
it is describing the old architecture. MiniMax is still genuinely used, but only by the
public and admin chat assistants.
