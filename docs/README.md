# docs/

Design notes, evidence and historical records.

**Read this first:** most of this folder predates the current build. The system went
through a significant architecture change - a FastAPI classification microservice was
removed and replaced with native n8n nodes, and the AI provider moved from MiniMax to
OpenAI for both AI steps. Documents written before that change describe an architecture
that no longer exists.

Rather than rewrite ~25 historical documents, they are labelled below. Nothing here is
deleted, because the audit trail is worth keeping.

## Where to actually look

| I want to... | Read |
|---|---|
| Install and run the project | [root `README.md`](../README.md) |
| Understand the design rationale | [`interview-prep/02-SUBMISSION-README.md`](../interview-prep/02-SUBMISSION-README.md) |
| Understand every node | [`interview-prep/03-PROJECT-WALKTHROUGH.md`](../interview-prep/03-PROJECT-WALKTHROUGH.md) |
| Import the workflows | [`workflow/noavia/PART1_IMPORT_GUIDE.md`](../workflow/noavia/PART1_IMPORT_GUIDE.md) |

## Current

Broadly accurate, with the caveat noted.

| Document | Subject | Caveat |
|---|---|---|
| `part1-current-readme.md` | Current Part 1 architecture | Refers to the ticket pipeline as `v1.json`; the current export is `v2.1.json` |
| `part1-current-checklist.md` | Delivery checklist | - |
| `part1-delivery-status.md` | Status summary | - |
| `decisions.md` | Architecture decision record | Long-lived; includes superseded decisions by design |
| `architecture-and-data-flow.md` | Data flow through the pipeline | Mentions the retired classification service |
| `code-tour.md` | Guided tour of the codebase | Mentions the retired classification service |
| `noavia-rag-evaluation.md` | RAG evaluation method and results | - |
| `n8n-paperclip-api-access.md` | n8n API access notes | - |
| `08_APPLICATION_FEATURES.md` | Feature inventory | Includes features beyond the Part 1 scope |

## Navigation aids

| Document | Subject |
|---|---|
| `00_START_HERE.md` | Original entry point. Superseded by the root README. |
| `01_BUILD_ORDER.md` | Suggested reading order |
| `99_DOC_ORDER.md` | Document ordering index |
| `getting-started.md` | Early setup guide. Superseded by the root README. |
| `testing-guide.md` | Early testing guide. Superseded by `tests/README.md`. |

## Historical

Accurate for the date written. **Describes the retired microservice architecture, the
MiniMax provider configuration, or both.** Do not use these to configure anything.

| Document | Subject |
|---|---|
| `README.legacy-platform.md` | The previous platform, explicitly retired |
| `noavia-part1-readme.md` | Superseded by `part1-current-readme.md` |
| `capability-module-architecture.md` | Module architecture from the microservice era |
| `noavia-final-report.md` | Report on the earlier implementation |
| `noavia-part1-checklist.md` | Earlier checklist |
| `noavia-functional-verification.md` | Verification evidence, earlier build |
| `noavia-isolated-readiness-evidence.md` | Isolated-run evidence, earlier build |
| `noavia-offline-delivery-evidence.md` | Offline delivery evidence, earlier build |
| `noavia-documentation-audit.md` | A documentation audit, itself now historical |
| `recovery-manifest.md` | Recovery notes from an earlier incident |

## Subfolders

| Folder | Contents |
|---|---|
| [`build/`](build/) | Step-by-step build notes captured during assembly |
| [`learning/`](learning/) | Personal study notes, predate the current architecture |
| [`audit-history/`](audit-history/) | Dated readiness audits, never updated after the fact |
| `archive/` | Retired material |

## Two facts that invalidate old documents

If a document says either of these, it is describing the old architecture:

1. **"The workflow calls a classification service over HTTP."** It does not. Both AI
   steps run through native n8n OpenAI nodes. The FastAPI service under
   `services/classification/` is retired.
2. **"MiniMax handles classification or draft generation."** It does not. Both use
   OpenAI `gpt-4o-mini`, and embeddings use `text-embedding-3-small`. MiniMax is still
   referenced by the public and admin chat workflows, which are outside the Part 1
   scope.
