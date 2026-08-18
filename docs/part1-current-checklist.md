# NOAVIA Part 1 - current acceptance checklist

Run commands from `C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.
This is the authoritative verification list for the native-n8n delivery.

## Offline checks

```powershell
python scripts/build_part1_workflow.py
python tests/test_noavia_workflow.py
python scripts/verify_part1_workflows.py
docker compose config --quiet
```

Success: five workflow tests pass, the verifier prints `PASS`, and Compose
returns exit code 0. Docker Desktop can emit its own credential-store warning;
that warning is not a Compose configuration failure.

Confirm the exports contain the required architecture:

- ticket intake requires name, email, subject, and message;
- PDF handling has parallel Drive and extraction branches, and extraction
  failure is non-blocking;
- classifier output is validated for category, urgency, sentiment, confidence,
  and summary;
- ingestion and retrieval both specify `text-embedding-3-small` / 1536;
- Qdrant collection is `noavia_kb_v1`, retrieval is top 3 with a threshold;
- the exact low-RAG fallback literal is present;
- Sheets receives the 19-column current schema (including the PDF Drive link)
  and customer email is never a
  delivery target.

## Owner-approved live checks

Follow [PART1_IMPORT_GUIDE.md](../workflow/noavia/PART1_IMPORT_GUIDE.md), then
[02_SAFE_N8N_TESTS.md](build/02_SAFE_N8N_TESTS.md). Before each live action,
obtain approval for its side effect:

1. Import both workflows **inactive**.
2. Bind n8n credentials and ingest the KB (OpenAI usage and Qdrant writes).
3. Refresh the supplied test Sheet's 19 headers, if required.
4. Route mail to a controlled inbox and run sample paths for high, medium,
   low, low-confidence, and damaged-PDF tickets.

Success is a Qdrant collection with points, one Sheet row per accepted ticket,
the specified routing behavior, a manual-review status below 0.6 confidence,
and no customer-directed email.
