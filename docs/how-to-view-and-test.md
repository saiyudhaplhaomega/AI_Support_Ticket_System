# How to view and test this project

Plain-language walkthrough for the project owner. It has two independent
parts: **Part A** works right now, needs no accounts, keys, or servers, and
proves the code is correct. **Part B** proves the *live* system (real n8n,
real Google Sheets, real email) works, and needs you to hold the credentials
— no agent in this project is allowed to hold or use them (see
[Why we built it this way](decisions.md#why-agents-never-hold-production-credentials)).

If you only do one thing after reading this, do Part A §1 — it takes two
minutes and needs nothing installed beyond Python.

## Where everything lives

Repository: <https://github.com/saiyudhaplhaomega/AI_Support_Ticket_System>

| Folder | What's in it |
|---|---|
| `workflow/noavia/` | The n8n workflow itself, exported as JSON, plus its own README |
| `knowledge-base/noavia/` | The 8 fictional FAQ/policy files the AI cites in replies |
| `services/classification/` | The classification + RAG microservice (talks to OpenAI/MiniMax and Qdrant) |
| `services/frontend/` | The demo ticket-submission form (has a safe "test mode") |
| `docker-compose.yml`, `Caddyfile`, `.env.example` | The full deployable stack definition |
| `tests/`, `evals/` | Automated offline test suites and the RAG accuracy evaluation |
| `docs/` | Everything you're reading now, plus architecture and evidence records |

To browse it without cloning anything, just open the GitHub links above in a
browser. To run anything below, clone it:

```sh
git clone https://github.com/saiyudhaplhaomega/AI_Support_Ticket_System.git
cd AI_Support_Ticket_System
```

---

## Part A — Test the code today (no accounts, no keys, ~10 minutes)

This proves the logic is correct: validation, AI-classification contract,
RAG retrieval/citation, routing rules, the manual-review override, and the
exact fallback sentence — all without touching a real n8n instance, a real
inbox, or a real spreadsheet.

### A1. Run the automated test suite (2 min)

```sh
python3 tests/test_noavia_workflow.py          # parses the 26-node workflow export, checks every rule
(cd services/classification && python3 -m pytest -q)   # 39 tests: classification/RAG service
(cd services/frontend && python3 -m pytest -q)          # 4 tests: the demo form
./scripts/verify-baseline.sh                    # infra contract: Qdrant auth, no secrets in n8n, upload-size limit
```

Expected: every command ends in `PASS` / `passed`, zero failures. As of the
last recorded run (2026-08-14) this is **45/45 tests passing** — see
[`docs/noavia-offline-delivery-evidence.md`](noavia-offline-delivery-evidence.md)
for the full dated record with exact output.

If any command fails, that's a real regression — stop and open an issue
before trusting anything downstream.

### A2. See it work in your browser (5 min)

This starts the actual ticket-submission form locally, in a mode that never
contacts n8n, email, Sheets, or any AI provider — it returns a canned,
realistic response so you can see the full shape of a result (classification
JSON, three cited sources, routing decision, processing log) without any
setup.

```sh
cd services/frontend
NOAVIA_TEST_MODE=true python3 -m uvicorn app:app --host 127.0.0.1 --port 8081
```

Open `http://127.0.0.1:8081/` in a browser, fill in the form with any dummy
name/email/message, submit. You'll get a deterministic `DEMO-0001` response
showing exactly what a real ticket's classification, RAG citations, and
draft reply look like. Stop the server with `Ctrl-C` when done.

### A3. Check the RAG accuracy numbers (2 min, optional)

```sh
python3 evals/noavia_rag_eval.py
```

Runs 40 fixed test queries against the knowledge base and writes
`evals/noavia_rag_eval_results.json`. This is checked into the repo already
— rerun it only if you want to reproduce the numbers yourself, and review
the diff before committing (it rewrites a tracked file). See
[`docs/noavia-rag-evaluation.md`](noavia-rag-evaluation.md) for what the
scores mean.

### What Part A does **not** prove

It does not prove Docker starts cleanly, that n8n can import/run the
workflow, that a PDF actually extracts, that Qdrant/OpenAI/MiniMax respond,
or that a Google Sheets row or Gmail message actually gets sent. That's Part B.

---

## Part B — Test the live, deployed system

This is the real end-to-end test: a browser submission travels through
Caddy → n8n → the classification service → Qdrant → back through n8n →
a real Google Sheets row and (for high/critical tickets) a real email.

**You need:** a server (or your existing VPS) with Docker, a domain name
pointed at it (for HTTPS via Caddy), an OpenAI API key, a MiniMax API key, a
Google Sheets OAuth connection, and a Gmail OAuth connection. Budget 30–60
minutes the first time.

### B1. Stand up the stack

```sh
cp .env.example .env
# edit .env: set N8N_PUBLIC_DOMAIN to your real domain, generate N8N_ENCRYPTION_KEY,
# fill in OPENAI_API_KEY, MINIMAX_API_KEY, and the AI_* / QDRANT_* keys — see the
# comments in .env.example next to each variable. Never commit this file.
docker compose up -d
docker compose --profile classification-service up -d --build
```

Verify containers are healthy:

```sh
docker compose ps
curl -s https://$N8N_PUBLIC_DOMAIN/healthz   # n8n should respond
```

### B2. Import and wire up the workflow

1. Open the n8n editor at `https://$N8N_PUBLIC_DOMAIN`, log in.
2. Import `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`
   (Workflows → Import from File). It imports **inactive** on purpose.
3. Bind the three credentials the export deliberately ships without values:
   - `Ingest Support Ticket` node — Header Auth credential (this is your
     webhook's shared secret; the export ships a placeholder ID by design).
   - `notify.google-sheets.v1` and `initialize.google-sheets-header.v1` —
     a Google Sheets OAuth2 credential scoped to **one** test spreadsheet.
   - `notify.routing-email.v1` — a Gmail OAuth2 credential scoped to an
     identity that can only send to your approved test/sink address.
4. Set `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` in the n8n environment so every
   route (including `default` and `manual_review`) maps to that one sink
   address — this is what stops a test ticket from ever emailing a real
   customer.

Full field-by-field detail: [`workflow/noavia/README.md`](../workflow/noavia/README.md).

### B3. Load the knowledge base into Qdrant

```sh
docker compose --profile classification-service exec classification-service \
  python3 -m app.ingest knowledge-base/noavia/
```

(Exact command name may differ — check
`services/classification/README.md` "Ingestion" section for the current
entrypoint.) Confirm the collection populated:

```sh
curl -s -H "Authorization: Bearer $AI_QDRANT_API_KEY" \
  http://localhost:6333/collections/noavia_kb_v1 | python3 -m json.tool
```

Expect `points_count: 8` (one per knowledge-base file).

### B4. Send one real test ticket

Activate the workflow in n8n, then:

```sh
curl -sS -X POST https://$N8N_PUBLIC_DOMAIN/webhook/noavia/tickets/v1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your header-auth secret>" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "I was charged twice",
    "message": "My card was billed twice for the same order this week."
  }'
```

**Check, in order:**

1. n8n → Executions: one new execution, no error nodes red.
2. Response JSON includes `category`, `urgency`, `sentiment`, `confidence`,
   a `summary`, and a `draft_reply` that cites `duplicate-charge.md`.
3. Your test Google Sheet: one new row with all 16 columns (ticket ID,
   timestamp, name, email, subject, category, urgency, sentiment,
   confidence, AI summary, draft response, knowledge sources, status,
   processing log).
4. Your test inbox: an email (duplicate-charge should classify as
   medium/high urgency, so this should fire).
5. Submit a second ticket with deliberately vague/off-topic text and confirm
   its Sheet row has `status = needs-manual-review` if confidence lands
   below 0.6, regardless of urgency.

**Immediately after:** deactivate the workflow again if you don't want it
publicly reachable between test sessions. n8n stores the deactivated state
in the `n8n_data` volume, so nothing is lost.

### What "everything is running fine" means at each stage

| You ran | What it proves | What it doesn't prove |
|---|---|---|
| Part A only | Logic is correct: validation, classification contract, RAG retrieval/citation, routing rules, fallback wording | Nothing about the deployed containers, real n8n, real Sheets/Gmail |
| Part A + B1–B3 | The stack starts and Qdrant is populated | The workflow hasn't actually processed a ticket yet |
| Part A + B1–B4 | **Full end-to-end proof** — a ticket really goes in, gets classified, retrieved, routed, logged, and delivered | Ongoing production reliability, retention, monitoring (see [Decisions §Open items](decisions.md#open-items-and-things-to-revisit)) |

## Troubleshooting

- **`docker compose up` fails on a missing var** — that's intentional
  fail-fast behavior (see [Decisions](decisions.md)); fill in the missing
  key in `.env` rather than adding a default.
- **Webhook returns 401** — the Header Auth credential in n8n doesn't match
  what you sent in `Authorization:`; re-bind it in step B2.
- **No Sheet row appears** — check the Google Sheets OAuth credential is
  bound on *both* `notify.google-sheets.v1` and
  `initialize.google-sheets-header.v1`, and that the spreadsheet ID in the
  node matches your test sheet.
- **No email arrives** — check `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` maps the
  ticket's route to a real address, and that the classified urgency is
  `medium` or above (low-urgency tickets are Sheets-only by design).
- **RAG citations look wrong / low confidence** — rerun `evals/noavia_rag_eval.py`
  and compare against the committed baseline in
  [`docs/noavia-rag-evaluation.md`](noavia-rag-evaluation.md); if you're
  still on the credential-free deterministic embedder instead of real OpenAI
  embeddings, wider separation is expected once you set
  `OPENAI_API_KEY` (see §7 of
  [`docs/noavia-final-report.md`](noavia-final-report.md)).

## Current status snapshot (last verified 2026-08-14)

- Part A: **done**, 45/45 offline tests passing, evidence in
  [`docs/noavia-offline-delivery-evidence.md`](noavia-offline-delivery-evidence.md).
- Part B: **not yet run** by any agent — no agent in this project holds
  production credentials or deployment approval, by design (see
  [Decisions](decisions.md)). The four remaining owner actions are listed in
  §6 of [`docs/noavia-final-report.md`](noavia-final-report.md). Once you
  complete B1–B4 yourself, this line should be updated with the date and
  outcome — that's the Documentation Agent's job, not a claim to make in
  advance of the evidence.
