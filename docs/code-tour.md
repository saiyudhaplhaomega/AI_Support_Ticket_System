# Code tour

> Historical platform note: this code tour predates the simplified native-n8n
> Part 1 stack. Use [00_START_HERE.md](00_START_HERE.md) and
> [part1-current-readme.md](part1-current-readme.md) for current instructions.

| Area | Primary locations | Evidence status |
| --- | --- | --- |
| Workflow | `workflow/noavia/workflow.noavia-ticket-pipeline.v2.1.json`, `tests/test_noavia_workflow.py` | **Verified:** inactive export and credential-free structural/Code-node harness. |
| Portal | `services/frontend/app.py`, `static/index.html`, `tests/test_app.py` | **Verified:** test-mode validation and synthetic acceptance. Controlled-live forwarding is **Configured but unexecuted**. |
| AI service API | `services/classification/app/main.py`, `schemas.py`, `security.py` | **Verified:** versioned endpoints and bearer-token boundary have offline tests. |
| Retrieval/ingestion | `services/classification/app/local_rag.py`, `ingest_cli.py`, `clients/` | **Verified:** local retrieval behavior is tested. Hosted model and Qdrant use are **Configured but unexecuted**. |
| Runtime declaration | `docker-compose.yml`, `Caddyfile`, `.env.example` | **Configured but unexecuted:** topology and environment contracts only. |
| Knowledge/evaluation | `knowledge-base/noavia/`, `evals/noavia_rag_eval.jsonl`, `evals/noavia_rag_eval.py` | **Verified:** fictional corpus and reproducible offline evaluation assets. |

See [Architecture and data flow](architecture-and-data-flow.md) for the cross-component path and [Testing guide](testing-guide.md) for test limits.
