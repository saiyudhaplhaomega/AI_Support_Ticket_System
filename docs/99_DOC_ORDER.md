# Reading order

If you are new to this project, read in this order. Each stage is useful on its own,
so you can stop wherever you have learned enough.

## Stage 1: what it is (about 30 minutes)

| # | Document | Why |
|---|---|---|
| 1 | [root `README.md`](../README.md) | What the system does, a worked example, and the pipeline diagram. Start nowhere else. |
| 2 | [`design-rationale.md`](design-rationale.md) | The four decisions that shaped it: architecture, AI output validation, RAG, what comes next |

## Stage 2: how it works

| # | Document | Why |
|---|---|---|
| 3 | [`workflow-walkthrough.md`](workflow-walkthrough.md) | Every node in the ticket pipeline and ingestion, in execution order. The main reference. |
| 4 | [`../workflow/noavia/README.md`](../workflow/noavia/README.md) | What each of the workflow files is for |
| 5 | [`08_APPLICATION_FEATURES.md`](08_APPLICATION_FEATURES.md) | Feature inventory across all the workflows, not just the ticket one |

## Stage 3: running it yourself

| # | Document | Why |
|---|---|---|
| 6 | [`../workflow/noavia/IMPORT_GUIDE.md`](../workflow/noavia/IMPORT_GUIDE.md) | Importing into n8n and binding credentials |
| 7 | [`build/02_SAFE_N8N_TESTS.md`](build/02_SAFE_N8N_TESTS.md) | Testing without hitting live Sheets, Drive or Gmail |
| 8 | [`how-to-view-and-test.md`](how-to-view-and-test.md) | Manual verification walkthrough |

## Stage 4: the code

| # | Document | Why |
|---|---|---|
| 9 | [`../scripts/README.md`](../scripts/README.md) | The workflow JSON is generated, not hand-edited. This explains the generator. |
| 10 | [`../tests/README.md`](../tests/README.md) | What the structural tests assert and how to run them |
| 11 | [`code-tour.md`](code-tour.md) | Short pointer map of the repository |

## Stage 5: the RAG side

| # | Document | Why |
|---|---|---|
| 12 | [`../knowledge-base/README.md`](../knowledge-base/README.md) | How the corpora are split and why |
| 13 | [`rag-evaluation.md`](rag-evaluation.md) | How the similarity threshold was calibrated |
| 14 | [`../evals/README.md`](../evals/README.md) | The evaluation harness itself |
| 15 | [`build/03_LIVE_KB_VERIFICATION.md`](build/03_LIVE_KB_VERIFICATION.md) | Checking the index against a live Qdrant |

## Reference, read when you need them

- [`decisions.md`](decisions.md) - architecture decision record, including superseded decisions
- [`architecture-and-data-flow.md`](architecture-and-data-flow.md) - short data-flow summary
- [`current-architecture.md`](current-architecture.md), [`delivery-status.md`](delivery-status.md),
  [`delivery-checklist.md`](delivery-checklist.md) - status snapshots
- [`build/04_VERCEL_GOOGLE_ADMIN.md`](build/04_VERCEL_GOOGLE_ADMIN.md) - frontend hosting and Google admin setup
- [`testing-guide.md`](testing-guide.md) - testing approach

## Skip unless you are digging into history

- [`00_START_HERE.md`](00_START_HERE.md), [`01_BUILD_ORDER.md`](01_BUILD_ORDER.md) and
  [`getting-started.md`](getting-started.md) are earlier entry points. They still
  describe the build order accurately, but the root README is more current for setup.
- [`../services/classification/README.md`](../services/classification/README.md) and
  [`../workflow/noavia/README.legacy-classification-service.md`](../workflow/noavia/README.legacy-classification-service.md)
  describe a **retired** microservice. The ticket workflow no longer calls it.
- `archive/legacy-platform/` is kept for traceability only.

## The one thing that dates a document

The system originally ran classification behind a FastAPI microservice, and used MiniMax
as the classifier. Both changed. Classification and drafting now run on native n8n OpenAI
nodes. If a document describes the ticket workflow calling a classification service over
HTTP, it is describing the old architecture. MiniMax is still genuinely used, but only by
the public and admin chat assistants.
