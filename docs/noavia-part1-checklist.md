# NOAVIA Part 1 — historical QA checklist

> **Historical reference only.** This long-form checklist was written for the
> retired classification-service/Caddy deployment. It is preserved for audit
> history, but its commands and criteria are not authoritative for the current
> native-n8n Part 1 build. Use [part1-current-checklist.md](part1-current-checklist.md)
> together with [build/02_SAFE_N8N_TESTS.md](build/02_SAFE_N8N_TESTS.md).

Scope: pre-execution verification matrix for NOAVIA Part 1. Every Part 1
requirement maps to a check below. Each check lists what it verifies, the
command / observation that proves it, and the expected PASS signal.

This is an **inspection** document. It does NOT execute the pipeline and
does NOT modify implementation files. A separate FINAL QA EXECUTION task
runs the live E2E after Tasks 1–3 land.

Frozen architecture (do not re-derive):

- Stack: `n8n (docker.n8n.io/n8nio/n8n:2.34.5)` + `Qdrant (qdrant/qdrant:v1.19.0)`
- Qdrant internal `http://qdrant:6333`, host port 6333, `/readyz`, auth disabled
- n8n host port 5678
- Embedding model: `text-embedding-3-small`
- Collection: `noavia_kb_v1`, top-K = 3
- Final submission: OpenAI for classification, grounded response draft, embeddings

---

## How to use

1. Mark each check PASS / FAIL with the observed evidence (command output,
   screenshot path, file:line reference).
2. Any FAIL blocks Part 1 sign-off. Document the failure as a separate
   `CHANGES REQUIRED` entry rather than fixing it inline.
3. Do not activate the workflow or run a controlled-live test from this
   checklist — execution requires owner approval and is owned by the
   FINAL QA EXECUTION task.

---

## A. Stack & compose

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| A1 | Compose file validates | `docker compose config --quiet` from repo root | exit code 0, no stderr |
| A2 | n8n image is pinned to `2.34.5` (no `:latest`) | `Select-String 'docker.n8n.io/n8nio/n8n:' compose.yaml` | line shows `:2.34.5` exactly |
| A3 | Qdrant image is pinned to `v1.19.0` (no `:latest`) | `Select-String 'qdrant/qdrant:' compose.yaml` | line shows `:v1.19.0` exactly |
| A4 | No `:latest` tag anywhere in compose | `Select-String ':latest' compose.yaml` | no matches |
| A5 | Qdrant healthcheck wired to `/readyz` | inspect `qdrant:` block `healthcheck.test` | contains `wget ... /readyz` (or `curl ... /readyz`) and `/readyz` is reachable from inside the container |
| A6 | Persistent volume for n8n | inspect `volumes:` and `n8n.volumes:` | named volume mounted to `/home/node/.n8n` |
| A7 | Persistent volume for Qdrant | inspect `qdrant.volumes:` | named volume mounted to Qdrant storage path |
| A8 | Self-contained networking | inspect `networks:` and per-service `networks:` | all services share a single private network; no service publishes Qdrant to host except the explicit `127.0.0.1:6333:6333` (or equivalent) for host-side verification, and that exception is documented |
| A9 | n8n host port 5678 reachable from reverse proxy or host | inspect `n8n.ports:` / `expose:` and `reverse-proxy.depends_on:` | n8n exposed on 5678 inside the stack; if behind reverse proxy, route exists in `Caddyfile` |
| A10 | `docker compose up -d` brings stack healthy | `docker compose ps` after up | both `n8n` and `qdrant` show `(healthy)` |

---

## B. Workflows

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| B1 | Ticket workflow JSON present | `ls -la workflow/noavia/workflow.noavia-ticket-pipeline.v1.json` | file exists, parses as valid JSON (`python -c "import json; json.load(open('workflow/noavia/workflow.noavia-ticket-pipeline.v1.json'))"`) |
| B2 | KB ingestion workflow JSON present | `ls -la workflow/noavia/workflow.noavia-kb-ingestion*.json` (or equivalent per repo convention) | file exists and parses as valid JSON |
| B3 | Both workflow JSONs importable into a fresh n8n | `POST /api/v1/workflows` with the JSON payload (against an isolated test n8n, not the live instance) | API returns 200, workflow listed with the imported node graph; credential refs are placeholders (`{id:"",name:""}`) so the import does not bind a foreign OAuth identity |
| B4 | Credential rebinding procedure is documented | `grep -nE "credential|Header Auth|OAuth" workflow/noavia/README.md` | README explicitly names: (a) Header Auth intake, (b) Google Sheets OAuth, (c) Gmail OAuth, and where each is bound (live n8n only, never in repo) |
| B5 | KB ingestion runs end-to-end and populates `noavia_kb_v1` | execute ingestion in isolated n8n; then `curl -s http://qdrant:6333/collections/noavia_kb_v1` | response shows `points_count` > 0; matches expected point count from `knowledge-base/noavia/` |
| B6 | Ingestion uses `text-embedding-3-small` | inspect ingestion HTTP node / classification-service env in use at runtime | ingestion call targets `text-embedding-3-small` (1536-dim) for Part 1; if classification-service is the embedder, `AI_EMBEDDING_MODEL=text-embedding-3-small` |
| B7 | Retrieval uses `text-embedding-3-small` | inspect the query/embed call invoked from the RAG lookup | same model and dimensions as ingestion (B6) |
| B8 | Retrieval returns top-3 chunks with a similarity threshold | inspect the RAG request payload + collection threshold | `top_k = 3` in request; `score_threshold` (or equivalent) defined; threshold value documented |

---

## C. Ticket pipeline (validation + intake)

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| C1 | Valid ticket accepted (name + valid email + subject + non-empty message) | `POST /webhook/noavia/tickets/v1` with full payload (isolated n8n) | 200, `ok:true`, Sheet row appended, classification fields populated |
| C2 | Malformed ticket rejected with clear error, no AI call | `POST` with missing subject and empty body | 400, `{ok:false, error:{code, message}}`; n8n execution log shows no call to classification endpoint; Sheet row count unchanged |
| C3 | PDF attached → extraction succeeds → processing continues | `POST` multipart with `data=<small PDF>` | 200, `attachment_name` populated, `rag_context` may include extracted text, Sheet row appended |
| C4 | PDF attached but extraction fails → processing continues with logged warning | `POST` multipart with a corrupted PDF (same field name) | 200, Sheet row appended, processing_log contains a warning that names the PDF extraction failure; classification still runs on `body` |
| C5 | Email validation rejects invalid format without AI call | `POST` with `requester_email: "not-an-email"` | 400, validation envelope; no AI call observed in execution log |

---

## D. Classification output shape

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| D1 | Classification returns `category` (one of the approved vocabulary) | inspect Sheet row | `category` ∈ {billing, technical, account, feature_request, complaint, other} |
| D2 | Classification returns `urgency` ∈ {critical, high, medium, low} | inspect Sheet row | value matches enum exactly |
| D3 | Classification returns `sentiment` | inspect Sheet row | value present (string or enum per classifier contract) |
| D4 | Classification returns `confidence` in [0, 1] | inspect Sheet row | numeric, `0 <= confidence <= 1` |
| D5 | Classification returns `ai_summary` (brief) | inspect Sheet row | non-empty short string |
| D6 | All five fields populated together for every accepted ticket | inspect N valid submissions | no row has any of the five missing or null |

---

## E. Routing

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| E1 | `critical` urgency → Sheets + detailed internal email | submit a critical-urgency ticket | Sheet row present; email sent to allow-listed recipient with detailed body (full draft + category + urgency + RAG citations) |
| E2 | `high` urgency → Sheets + detailed internal email | submit a high-urgency ticket | same as E1 |
| E3 | `medium` urgency → Sheets + brief internal email | submit a medium-urgency ticket | Sheet row present; email sent with a brief body (short summary, no full draft) |
| E4 | `low` urgency → Sheets only | submit a low-urgency ticket | Sheet row present; no email sent (or no email-sent record in logs) |
| E5 | `confidence < 0.6` → `status = needs-manual-review` regardless of urgency | submit a low-confidence ticket (force by stub or fixture) | Sheet `status` field equals `needs-manual-review`; routing still produces a row, with email behavior per the approved rule for manual review |
| E6 | Single recipient across all routes | inspect `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` in the deploy plan | exactly one recipient appears in all 8 routes (default + 6 categories + manual_review) |

---

## F. Google Sheets row contract

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| F1 | Header row contains all 14 required columns | inspect the destination tab header | every column present in this order (or a documented superset): `ticket_id, timestamp, name, email, subject, category, urgency, sentiment, confidence, ai_summary, draft_response, kb_sources, status, processing_log` |
| F2 | Every accepted ticket appends one row | run N valid submissions | row count delta == N; no duplicate rows for the same `ticket_id` |
| F3 | `processing_log` is populated on the row | inspect a row | contains a non-empty JSON or text array of log events for that ticket |
| F4 | `error_code` / `error_message` columns (if present in schema) are populated only on error rows | inspect failed and successful rows | empty for success; non-empty with a code from the documented envelope on failure |
| F5 | Test-mode-only discipline | inspect workflow + portal config | writes only target the test sheet (`NOAVIA Support Tickets - Test`); production sheet id never referenced |

---

## G. Email delivery

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| G1 | Internal email is sent when required (critical / high / medium) | inspect Gmail node execution logs for E1–E3 | one email per submitted critical/high/medium ticket, recipient from allow-list |
| G2 | Internal email is NOT sent for `low` urgency | inspect Gmail node execution log for E4 | zero emails recorded for the low-urgency run |
| G3 | NO draft email is auto-sent to the customer | grep workflow + portal code for customer-facing send paths; inspect execution log | no `sendTo` resolves to `requester_email`; no Gmail node targeting customers; execution log shows zero customer-bound sends |
| G4 | Sender cannot be set from ticket fields | inspect Gmail node configuration | `sendTo` expression reads only from server-side allow-list; no expression reads `requester_email`, `from_email`, `default_route_email`, `routing_emails` |
| G5 | Recipient cannot be set from ticket fields | same as G4 | same conclusion |
| G6 | Delivery error produces logged envelope | force a Sheets or Gmail failure (e.g. revoke credential mid-run in isolated n8n) | workflow returns 502 with `DELIVERY_ERROR` envelope; Sheet `error_code` populated |

---

## H. Low-similarity fallback (RAG)

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| H1 | Low-similarity fallback uses the exact literal | submit a query with no KB match; inspect `draft_response` (or equivalent grounded-response field) | literal string `"No specific policy found — this response is based on general knowledge."` appears verbatim — em dash (U+2014), no extra whitespace, no trailing punctuation added |
| H2 | Fallback still records `kb_sources` | inspect same row | `kb_sources` either empty / below threshold marker (per repo convention) but still present as a column |
| H3 | Threshold value is documented | inspect RAG node config and `docs/decisions.md` | threshold value named; matches the value used at runtime |

---

## I. Architecture hygiene

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| I1 | No classification-service runtime dependency in the ticket pipeline | `grep -nE "classification-service|http://classification-service" workflow/noavia/*.json` | if the ticket pipeline embeds classification via direct OpenAI calls (per Part 1 architecture), zero matches; if classification-service is reused, the call surface is the published HTTP contract only |
| I2 | No `ai.classify-ticket.v1` / `ai.rag-lookup.v1` references remain in the active ticket pipeline | `grep -nE "ai\\.classify-ticket\\.v1\|ai\\.rag-lookup\\.v1" workflow/noavia/workflow.noavia-ticket-pipeline.v1.json` | no matches (the names appear only in historical evidence docs) |
| I3 | No `AI_CLASSIFY_API_KEY` bearer middleware remains in the active path | `grep -nE "AI_CLASSIFY_API_KEY\|AI_CL...EY" workflow/noavia/workflow.noavia-ticket-pipeline.v1.json` | no matches in workflow JSON; bearer secret lives in classification-service only (or is unused per Part 1) |
| I4 | `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` declared in repo compose (not live-only) | inspect `n8n.environment:` in `docker-compose.yml` | the env var is present with rationale comment if the workflow reads `$env.*` in Code nodes |
| I5 | `AI_QDRANT_API_KEY` is NOT injected into n8n | inspect `n8n.environment:` | absent; only `classification-service.environment:` carries it (if used) |
| I6 | Qdrant credentials live only with the data store and the classification service | inspect `qdrant.environment:` and `classification-service.environment:` | Qdrant holds the signing/admin key; classification-service holds the scoped JWT; n8n has neither |

---

## J. Reproduction (README fresh-instance procedure)

| # | Check | Command / observation | PASS signal |
|---|---|---|---|
| J1 | README has a fresh-instance procedure | `grep -nE "clone|git clone\|compose up\|import\|rebind\|ingest\|sample" README.md docs/how-to-view-and-test.md` (whichever is canonical) | the six steps appear in order: clone → compose up → import → rebind → ingest → submit sample → verify |
| J2 | Procedure is reproducible on a clean checkout | follow the README on a fresh clone (separate VM or worktree) | every command completes without undocumented manual edits; the seven terminal-state checks (A10, B5, C1, D6, E1–E4, F2, G1) PASS |

---

## K. Out-of-scope (recorded for the FINAL QA EXECUTION task)

These are intentionally NOT executed here. They belong to the live E2E
task, which has its own owner-approval gate.

- Live submission to the production n8n instance
- Owner-approved controlled-live test with real Gmail / Sheets side effects
- Real OpenAI embedding ingestion (vs deterministic stub)
- Load, latency, and concurrency measurements
- Customer PII handling audit

---

## L. Sign-off table

| Section | PASS / FAIL | Evidence reference | Reviewer |
|---|---|---|---|
| A. Stack & compose | | | |
| B. Workflows | | | |
| C. Validation + intake | | | |
| D. Classification shape | | | |
| E. Routing | | | |
| F. Sheets row contract | | | |
| G. Email delivery | | | |
| H. RAG fallback | | | |
| I. Architecture hygiene | | | |
| J. Reproduction | | | |

Part 1 PASS criterion: every row in every section is PASS with evidence,
AND no FAILs in K (K items are deferred, not failed).
