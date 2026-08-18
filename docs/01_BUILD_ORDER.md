# NOAVIA Part 1 - build order

Run every command below from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.

1. Start the local stack: `docker compose up -d`.
   Verify with `docker compose ps`; n8n, Qdrant, and the frontend should be
   running. Open `http://localhost:8081` to see the public ticket page. The
   administrator pages are `/admin/login` and `/admin/knowledge-base`.
2. In n8n, import `workflow/noavia/workflow.noavia-kb-ingestion.v1.json`.
   Bind its OpenAI and Qdrant credentials, then run it manually.  Verify with
   `curl.exe http://localhost:6333/collections/noavia_kb_v1`; the collection
   must have points.
3. Import `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`.  Bind the
   Header Auth, OpenAI, Qdrant, Google Sheets, Google Drive, and Gmail
   credentials.  Set the Sheet node to the NOAVIA test spreadsheet, not a
   customer sheet.
4. Follow [build/02_SAFE_N8N_TESTS.md](build/02_SAFE_N8N_TESTS.md) only after
   the notification recipient is a test inbox. A successful run returns
   `ok: true`, appends one Sheet row, and never sends the generated draft to
   the requester.

Why this order: retrieval only works once the ingestion workflow has created
the matching 1536-dimension collection and indexed the knowledge files.

## Local test command

From `C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`, create
one isolated environment and run all credential-free checks:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services\frontend\requirements.txt
.\.venv\Scripts\python.exe -m pytest -q services\frontend\tests
.\.venv\Scripts\python.exe tests\test_noavia_workflow.py
python scripts\verify_workflows.py
```

Expected result: frontend tests pass, workflow tests report `OK`, and the
workflow verifier prints a `PASS` contract line. The virtual environment keeps
dependencies out of the system Python and uses aligned FastAPI, Uvicorn, and
Pydantic versions for the portal. Continue with
[build/03_LIVE_KB_VERIFICATION.md](build/03_LIVE_KB_VERIFICATION.md) before
calling RAG complete.
