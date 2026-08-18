# NOAVIA Part 1 delivery status

The repository export now contains the two workflow artifacts required for the
interview: `workflow.noavia-ticket-pipeline.v2.1.json` and
`workflow.noavia-kb-ingestion.v1.json`.

Run the following from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`:

```powershell
python scripts/build_workflow.py
python scripts/verify_workflows.py
docker compose config --quiet
```

Expected result: the workflow verifier reports `PASS`, and Compose exits with
code 0. The verifier is intentionally credential-free; it proves the exported
node graph implements the required contracts but does not claim that external
OpenAI, Qdrant, Google Sheets, or Gmail calls have run.

Local verification completed on 2026-08-17: 49 classification-service tests,
8 frontend tests, 5 workflow acceptance tests, and the export verifier passed.
These checks do not replace the controlled live validation below.

## Live deployment sequence

1. Import the KB workflow, bind Qdrant/OpenAI credentials, and run it.
2. Verify Qdrant collection `noavia_kb_v1` has points.
3. Import the ticket workflow, then bind Header Auth, OpenAI, Qdrant, Google
   Drive, Google Sheets, and Gmail credentials.
4. In `notify.google-sheets.v1`, refresh the target Sheet schema so it uses
   the 18 exported columns. Run its disabled header-initialization branch once
   only on the test sheet.
5. Map every notification route to a controlled test inbox before activating
   the ticket webhook.
6. Execute the four safe paths in [build/02_SAFE_N8N_TESTS.md](build/02_SAFE_N8N_TESTS.md).

The current published live workflow must be replaced because its classifier
HTTP response did not reach the structured parser, which caused the fallback
branch to run even after OpenAI returned a response. The repaired export is
ready, but no claim is made here that it has been imported, activated, or run
against external services.
