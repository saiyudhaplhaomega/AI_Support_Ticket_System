# NOAVIA AI Support Ticket System — Part 1

This repository contains the current, reproducible interview implementation.
Start with [the guided build sequence](docs/00_START_HERE.md), then read the
[current Part 1 architecture](docs/part1-current-readme.md).

## Quick verification

From `C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`, run:

```powershell
python scripts/build_part1_workflow.py
python tests/test_noavia_workflow.py
python scripts/verify_part1_workflows.py
docker compose config --quiet
```

The workflow tests and verifier must pass, and Compose must validate. To start
the local n8n + Qdrant stack after configuring your credentials, run
`docker compose up -d`.

The two n8n exports and exact credential/import steps are in
[workflow/noavia/PART1_IMPORT_GUIDE.md](workflow/noavia/PART1_IMPORT_GUIDE.md).
No secrets are committed. Importing, ingesting the knowledge base, writing
Google Sheets rows, and sending internal mail are intentionally owner-gated
because they change external services.

The recovered earlier platform documentation is preserved at
[docs/README.legacy-platform.md](docs/README.legacy-platform.md); it is not
the current Part 1 deployment guide.
