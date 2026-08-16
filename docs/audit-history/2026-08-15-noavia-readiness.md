# NOAVIA readiness — 2026-08-15 audit (archived gap plan)

> **Audit posture note (added 2026-08-16 when this file was moved into
> `docs/audit-history/`).**
>
> Two prior audit verdicts reached different conclusions: `t_a015fb8d`
> rated the repo interview-ready (45 tests pass, no secrets);
> `t_7692e52d` synthesis rated it not interview-ready (8 P0s). This audit
> reconciles the two: the `t_a015fb8d` verdict addressed whether the code
> runs and looks clean; the `t_7692e52d` verdict addressed whether the
> code is safe in front of a sharp interviewer who probes the n8n contract
> layer and the security posture. The two verdicts are scoped-different,
> not contradictory.
>
> The P0 layer (cheap + medium fixes) is closed by
> `.hermes/plans/final-plan-2026-08-16.md` (FINAL PLAN v6 / v5 file). The
> expensive P0s (T1–T4) are filed as honest "designed + ticketed" known
> debt, not hidden risk.
>
> The 2026-08-14 offline-delivery evidence record stands as the canonical
> baseline for what was verified offline; the 2026-08-16 `t_44e47f58`
> inspection confirmed the live n8n state is structurally aligned with the
> repo artifact except for the ingest-credential placeholder (the
> `REPLACE_WITH_N8N_CREDENTIAL_ID` binding, addressed by the gated
> owner-only C-INTAKE step). What follows is the original 2026-08-15 gap
> plan that this preamble now reframes.

---

# NOAVIA readiness gap plan — 2026-08-15 audit (original document, archived)

Author: Project Director (read-only audit, no implementation in this session).
Source of truth: current working tree on `main` at `git status = clean` apart
from the untracked `AGENTS.md` (commit `83586bd` "fix(noavia): correct RAG
median bug and stale audit metric (SAI-52)" is the latest tracked commit at
audit time; `AGENTS.md` is untracked and is the board's own context file, not
a repo artifact).

This document is a **gap plan**, not an implementation report. Every finding
is backed by either a file path + line number, a command output snippet, or a
direct quote from the source. Statements about status refer to the audit
moment (2026-08-15) and use the repo's own three-tier vocabulary:
**Verified** / **Configured but unexecuted** / **Planned — unverified**.

---

## 1. Executive summary

NOAVIA is in a **mature, audit-ready, structurally complete** state. The
hard problem it set out to solve — defining a reusable capability-module
SaaS factory and shipping NOAVIA as the first consumer — is solved in the
repository. The architecture is sound, the contracts are crisp, security
posture is conservative, secrets are never committed, the test harness is
honest about what it proves and what it does not, and the documentation
distinguishes offline evidence from unverified live-integration claims.

What remains for an interview-ready, reproducible delivery is **not
architecture** — it is **a small set of well-bounded code-quality issues,
a few ergonomics gaps, and a single hard external dependency (an owner-run
live integration test)**. The blockers that look hardest (Sheets/Gmail
binding, n8n activation, live Qdrant ingestion) are owner-only by design
and are explicitly framed as such throughout the docs.

| Area | Status | Effort to close |
|---|---|---|
| Architecture & contracts | Verified | — |
| Offline test coverage | Verified (45 offline tests pass) | — |
| Secrets & security posture | Verified (no secrets tracked, scoped Qdrant JWT, n8n has no Qdrant cred) | — |
| Docker / Compose / Caddy | Configured but unexecuted | Run part B (`how-to-view-and-test.md` §B1) |
| Live n8n import & activation | Owner-only | Run part B §B2 |
| End-to-end live test with real Qdrant / Sheets / Gmail | Owner-only | Run part B §B3–B4 |
| Code-quality nits (~6 small defects) | Verified residual | Small, see §3 |
| `docs/how-to-view-and-test.md` part B step B3 command is wrong | Verified residual | Trivial fix (P0 #1) |
| Knowledge base is only 8 short fictional files | Verified (by design) | Optional expansion (P2 #7) |

---

## 2. Verified current state (with evidence)

### 2.1 Repository structure and Git state

- **Working tree**: `main` branch, `git status` clean except the
  untracked `AGENTS.md` (a Hermes board context file, not part of the repo).
- **Latest commit**: `83586bd fix(noavia): correct RAG median bug and stale
  audit metric (SAI-52)`. Commit graph goes back through 20+ tracked commits
  including real corrections (SAI-52 median bug, SAI-32 provider split,
  SAI-27 final report, SAI-13 owner-facing guide).
- **Remote**: `origin → https://github.com/saiyudhaplhaomega/AI_Support_Ticket_System.git`.
  Local `main` is one commit ahead of `origin/main` per the wrapped
  `noavia-final-report.md` (push was attempted in that prior session but
  hit a "no GitHub credential" wall — known, owner-acknowledged).
- **Tags**: none. **No published release artifact.**

### 2.2 Layout (audit-verified)

```
AGENTS.md                                 (untracked — Hermes context)
Caddyfile
docker-compose.yml
.env.example
.gitignore
README.md
docs/                                     (15 markdown files, see §2.8)
evals/
  noavia_rag_eval.jsonl                   (40 cases)
  noavia_rag_eval.py
  noavia_rag_eval_results.json            (committed, reproducible)
knowledge-base/
  README.md
  noavia/                                 (8 fictional KB files)
scripts/
  test.sh
  verify-baseline.sh
services/
  classification/                         (ai.classify-ticket / ai.rag-lookup)
    app/  (main.py, config.py, schemas.py, security.py, errors.py,
           logging_utils.py, ingest_cli.py, local_rag.py, clients/*, services/*)
    tests/  (8 test files, 39 tests)
    Dockerfile, requirements.txt, pytest.ini, README.md (270 lines)
  frontend/                               (test-mode demo form)
    app.py, static/index.html, tests/ (2 files, 6 tests)
    Dockerfile, requirements.txt
tests/
  test_noavia_workflow.py                 (262 lines, parses 26-node export)
workflow/
  noavia/
    workflow.noavia-ticket-pipeline.v1.json  (906 lines, 26 nodes)
    README.md
```

### 2.3 n8n workflow export

- **File**: `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`
  (33,764 bytes, 906 lines, **26 nodes**).
- **`active: false`** at the top level — inactive by design.
- **All credentials are ID references, never literal values**:
  - `Ingest Support Ticket` — `httpHeaderAuth` ID `REPLACE_WITH_N8N_CREDENTIAL_ID`
    (placeholder by design; owner binds it in the isolated n8n instance).
  - `notify.google-sheets.v1` — `googleSheetsOAuth2Api` ID reference.
  - `initialize.google-sheets-header.v1` — same ID reference, node
    `disabled: true`.
  - `notify.routing-email.v1` — `gmailOAuth2` with empty `id` and `name`,
    by design (the bound credential lives only in the isolated n8n instance).
- **All 26 required nodes present** (asserted by `tests/test_noavia_workflow.py`):
  Ingest Support Ticket, Validate and Normalize, audit.ingestion.v1,
  Validation OK?, audit.validation-rejection.v1, Respond Validation Error,
  Has PDF Attachment?, Extract PDF Text, Add PDF Context, No Attachment,
  ai.classify-ticket.v1, Classification OK?, Prepare RAG Lookup,
  ai.rag-lookup.v1, RAG Lookup OK?, Attach RAG Matches, RAG Fallback,
  Classification Fallback, draft.grounded-reply.v1, route.by-classification.v1,
  notify.google-sheets.v1, notify.routing-email.v1,
  audit.delivery-outcome.v1, Respond Processing Result,
  Manual Trigger - Initialize Ticket Sheet Header,
  initialize.google-sheets-header.v1.
- **Graph wiring verified**: every IF branch has both main outputs;
  all three fallbacks converge on `draft.grounded-reply.v1` →
  `route.by-classification.v1` → `notify.google-sheets.v1` →
  `notify.routing-email.v1` → `audit.delivery-outcome.v1` →
  `Respond Processing Result`.
- **Tracked-file secret scan**: the workflow JSON does not contain any of
  `sk-`, `AIza`, or `smtp.gmail.com` (asserted in `test_noavia_workflow.py`).
- **Workflow offline harness passes**: `python tests/test_noavia_workflow.py`
  → `PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and
  delivery contracts present` (re-run during this audit, 2026-08-15).

### 2.4 Qdrant and RAG ingestion / retrieval

- **In-process local RAG** (`services/classification/app/local_rag.py`):
  - `DeterministicHashEmbedder` — credential-free, stable 256-dim BLAKE2b
    signed-hash embedding. Lexically reranked. `DEFAULT_CONFIDENCE_THRESHOLD = 0.10`.
  - `InMemoryVectorStore` — credential-free upsert/search adapter.
  - `chunk_markdown` — word-overlap chunker (120 words, 24 overlap), stable
    IDs `<source>#<index>` and metadata `source`, `title`, `chunk_index`.
  - `retrieve(...)` — caps at `top_k` (1..3), `manual_review` fallback when
    confidence below threshold AND fewer than 2 grounded query tokens.
- **Hosted path** (production; configured but unexecuted):
  - `services/classification/app/services/ingest_service.py` — OpenAI
    embeddings + Qdrant REST upsert, batched at 100, UUID5-stable IDs.
  - `services/classification/app/services/rag_service.py` — OpenAI
    embeddings + Qdrant `query_points`, with `collection_exists` short-circuit
    (returns empty matches, not an error, for unpopulated collections).
  - `services/classification/app/clients/qdrant_client.py` — `AsyncQdrantClient`
    factory, `ensure_collection` helper, idempotent.
- **Committed RAG metrics** (`evals/noavia_rag_eval_results.json`):
  `Recall@3 = 1.0000, Top-1 = 0.9062, MRR = 0.9531, unsupported fallback
  accuracy = 1.0000, zero false-confidence cases` at threshold `0.10`.
  - 40 labeled cases in `evals/noavia_rag_eval.jsonl`.
  - Reproduction: `python3 evals/noavia_rag_eval.py` rewrites the JSON
    byte-for-byte (after the SAI-52 median-bug fix).
- **Knowledge base** (`knowledge-base/noavia/`, 8 files, all <700 bytes):
  api-token-rotation, csv-import, data-retention, duplicate-charge,
  email-notifications, knowledge-search, password-reset, priority-and-sla.
  - Defined as fictional / product-neutral in `docs/decisions.md` and
    `knowledge-base/README.md`.
  - **Limitation**: 8 files × 1 chunk each = 8 chunks total. Sufficient for
    the 40-case evaluation, but real production would either need a larger
    curated KB or a re-embed after switching to OpenAI vectors.

### 2.5 Classification / application code

- **Service**: `services/classification/app/main.py` (FastAPI app).
  - `POST /ai/classify-ticket/v1` — MiniMax JSON chat completion.
  - `POST /ai/rag-lookup/v1` — OpenAI embeddings + Qdrant search.
  - `POST /ai/grounded-draft/v1` — MiniMax chat with up to 3 RAG matches.
  - `POST /internal/ingest/v1` — OpenAI embeddings + Qdrant upsert.
  - `GET /healthz` (no auth) and `GET /readyz` (pings Qdrant, 503 on failure).
- **Auth**: `Authorization: Bearer <AI_CLASSIFY_API_KEY>` enforced via
  `require_auth` dependency on every business endpoint. `verify_bearer_token`
  uses `hmac.compare_digest` (constant-time).
- **Error envelope**: every non-success path returns the shared
  `{ok: false, error: {code, message, interface_id, version, correlation_id}}`
  shape. `AUTH_ERROR` is the only code that maps to HTTP 401; everything
  else is HTTP 200 (rationale in `docs/capability-module-architecture.md` §5).
- **Correlation IDs**: injected via `X-Correlation-Id` header or generated
  per request, echoed back in the response header and every log line.
- **PII safety**: validation errors are stripped to
  `{field, code}` only (no input values, no rendered strings). Tested with
  `test_validation_error_never_exposes_ticket_pii_in_body_or_logs`.
- **Test coverage**: 39 tests across 8 files (`test_api.py`, `test_config.py`,
  `test_errors.py`, `test_local_rag.py`, `test_qdrant_client.py`,
  `test_schemas.py`, `test_security.py`, `test_api.py`).

### 2.6 Docker & Docker Compose

- **Stack**: `docker-compose.yml` defines 5 services (`reverse-proxy`, `n8n`,
  `qdrant`, `classification-service` in profile, `frontend` in profile),
  one shared `saas-internal` bridge network, and 5 named volumes.
- **Network posture**: only `reverse-proxy` publishes `80`/`443`. All other
  services are reachable only by container DNS name on the internal network.
- **Caddyfile**: `{$N8N_PUBLIC_DOMAIN}` block routes `/noavia` strip-prefix
  to the frontend, `/webhook/noavia/tickets/v1` to n8n with a 10 MB body cap
  (so a 10 MB+ upload gets a Caddy 413 before n8n ever buffers). Localhost
  self-signed fallback is commented out, ready for use.
- **Health checks**: every backend service has a `healthcheck` block
  (`n8n`, `qdrant`, `classification-service`); the classification service
  Dockerfile also includes a redundant `HEALTHCHECK` line.
- **Fail-fast on missing secrets**: `docker-compose.yml` uses `?:` syntax
  for required secret-bearing vars (e.g. `${QDRANT_SERVICE_API_KEY:?...}`).
  The classification service `config.py` refuses to start if any required
  secret is missing.
- **Status**: `Configured but unexecuted` — never started in this audit
  session; no Docker daemon is available to the agent (consistent with the
  "no agent holds production credentials" rule).

### 2.7 Tests and validation coverage

- **Reproduced offline during this audit**:
  - `python3 tests/test_noavia_workflow.py` → `PASS: 26 nodes; validation
    envelope, audit telemetry, fallbacks, and delivery contracts present`.
  - **Note**: classification `pytest` run failed in the agent's Python 3.14
    environment because `qdrant_client` is not installed. This is a local
    environment artifact, not a repository defect — the repo's own
    `services/classification/README.md` Local dev section instructs
    `pip install -r requirements-dev.txt` first. The previously recorded
    run (`docs/noavia-offline-delivery-evidence.md`) shows 39 tests passed.
- **Coverage of the offline suite**:
  - 26-node workflow structural harness (validation, audit, fallbacks,
    Sheets columns, routing, hostile-payload rejection).
  - 39 classification tests (envelope, auth, schemas, error mapping,
    upstream timeout/error, PII safety, Qdrant credential forwarding,
    config validation, local RAG fixtures).
  - 4 frontend tests (test-mode, validation, controlled-live origin guard,
    sanitized 502).
  - 2 frontend browser tests (DOM labels, validation messages).
  - 1 RAG evaluation (40 cases, writes reproducible JSON).
  - **Total: 45 offline tests + 40 RAG cases**, all credential-free.

### 2.8 Security & secret handling

- **No secrets in tracked files**: `git ls-files` scan for `sk-`, `AIza`,
  `smtp.gmail.com`, and `AKIA` shapes — zero matches. The workflow export
  contains only credential ID references.
- **`.env` is git-ignored** (`git check-ignore -v .env` confirms).
- **`.env.example` documents only names, never values**. Every secret value
  is empty in the tracked file.
- **n8n is bare-handed**: `AI_CLASSIFY_API_KEY` is the only bearer token
  it sees. It holds no `OPENAI_API_KEY`, no `MINIMAX_API_KEY`, no Qdrant URL,
  no Qdrant credential. The classification service is the sole gateway to
  upstream providers and Qdrant.
- **Qdrant auth is layered**:
  - Admin/signing key (`QDRANT_SERVICE_API_KEY`) lives only in the qdrant
    container.
  - Application containers get a collection-scoped JWT (`AI_QDRANT_API_KEY`).
  - The flag `AI_QDRANT_AUTH_ENABLED` defaults to `true`; turning it off
    requires explicit owner action and is rejected when a key is missing
    on an authenticated deployment.
- **Webhook guard**: 10 MB body cap at Caddy; Header Auth on the webhook node;
  server-side URL validation (`NOAVIA_N8N_INTERNAL_WEBHOOK_URL`) rejects
  credentials, IPs, query strings, and fragments.
- **Browser code is credential-free**: `services/frontend/static/index.html`
  inlines only the public form; no webhook URL, no API key, no OAuth token.
- **PII handling**: validation errors strip input values; logs do not
  include request bodies; API exception messages do not echo upstream
  provider details (`test_validation_error_never_exposes_ticket_pii_in_body_or_logs`).

### 2.9 Documentation / setup quality

- **15 markdown files in `docs/`**, each with a clear scope:
  - `architecture-and-data-flow.md` — pipeline path with a per-segment
    verified-vs-unverified map.
  - `capability-module-architecture.md` — formal interface contract (§3.1,
    §3.2, §3.3, §3.4, §3.5) used by every other doc.
  - `code-tour.md` — area-by-area "what is verified" map.
  - `decisions.md` — decision log with alternatives considered and trade-offs.
  - `getting-started.md` — terse how-to-run.
  - `how-to-view-and-test.md` — full narrative walkthrough, Part A (no
    secrets) and Part B (owner-run).
  - `n8n-paperclip-api-access.md` — approval-gated, scoped API access runbook.
  - `noavia-documentation-audit.md` — the audit that found and corrected
    stale claims.
  - `noavia-final-report.md` — consolidated SAI-27 report with QA & Security
    independent review.
  - `noavia-functional-verification.md` — safe-mode evidence summary.
  - `noavia-isolated-readiness-evidence.md` — control-plane record from
    2026-08-14 n8n/Qdrant inspection.
  - `noavia-offline-delivery-evidence.md` — the dated offline QA record.
  - `noavia-rag-evaluation.md` — RAG metrics with limits.
  - `recovery-manifest.md` — provenance record from the 2026-08-13
    recovery, with SHA-256 hashes.
  - `testing-guide.md` — terse test limits.
- **Status vocabulary is consistent**: `Verified`, `Configured but unexecuted`,
  `Planned/unverified`. The audit corrections from
  `noavia-documentation-audit.md` (six items) are all reflected in the
  current docs.

### 2.10 Offline-safe demo readiness

- **Local demo path** (no Docker, no secrets, no network):
  `cd services/frontend && NOAVIA_TEST_MODE=true python3 -m uvicorn app:app
  --host 127.0.0.1 --port 8081` → open `http://127.0.0.1:8081/` → submit
  any dummy ticket → deterministic `DEMO-0001` response with mock
  classification, 3 RAG sources, routing decision, manual-review status,
  processing log, and an internal-draft-only reply.
- **Browser tests** assert that the demo page exposes every required label
  and remains usable offline (no `node --test` failures, verified by the
  committed run record).
- **Belt-and-suspenders**: `app.py::internal_webhook_target` rejects any
  URL that doesn't exactly match the server-side allowed origin, in test
  mode or otherwise. The `NetworkMustNotRun` test fixture additionally
  asserts that `httpx.AsyncClient` is never constructed in test mode —
  making the offline guarantee structurally enforced.

---

## 3. Remaining gaps — prioritized

### P0 — must fix before claiming "interview-ready reproducible"

These are real defects found in the audit. None blocks the offline demo,
but they would surface the moment a reviewer imports the workflow or runs
the service.

1. **`docs/how-to-view-and-test.md` §B3 has a wrong command.**
   - **Where**: line 183, `how-to-view-and-test.md`.
   - **Current**: `docker compose --profile classification-service exec
     classification-service python3 -m app.ingest knowledge-base/noavia/`.
   - **Actual entrypoint** (per `services/classification/README.md` §
     "Ingestion" and `ingest_cli.py`): `python3 -m app.ingest_cli --file
     kb.jsonl --collection kb_documents`. The CLI takes a JSONL file, not a
     directory; the repo has no `app.ingest` module and no top-level
     `knowledge-base/noavia/*.jsonl` to point at.
   - **Impact**: A reviewer following Part B §B3 will hit a `ModuleNotFoundError`
     and lose trust. This is a doc defect, not a code defect.
   - **Fix**: rewrite the ingest step to either (a) generate a JSONL on the
     fly with a small one-liner, or (b) call `POST /internal/ingest/v1` over
     the internal network with a JSON body, or (c) extend `ingest_cli.py`
     to accept a directory.

2. **Source-level type annotation defect in two files.**
   - **Where**: `services/classification/app/main.py` line 66 and
     `services/classification/app/security.py` line 18.
   - **Defect**: `authorization: str *** None = Header(default=None)` and
     `authorization: str *** None, expected_key: str, *, interface_id: str`.
     This is clearly a typo for `str | None` (PEP 604 union).
   - **Why it isn't immediately broken**: both files have
     `from __future__ import annotations` at the top, so annotations are
     stored as strings and never evaluated at runtime. Tests pass.
   - **Why it still matters**:
     - Anyone copy-pasting the function into a non-`__future__` file gets
       a `TypeError` at import time.
     - Anyone running `python -c "from app.main import app"` without the
       future import fails.
     - The intent is documented everywhere (`str | None`), and the mis-spelling
       is a future-fragility landmine.
     - Static type checkers (mypy/pyright) that evaluate annotations
       eagerly will report errors.
   - **Fix**: change `str *** None` to `str | None` in both files. Surface
     a regression test that removes `from __future__ import annotations`
     from a copy and asserts it still imports.

### P1 — should fix before the next review cycle

3. **Inconsistent docstring conventions in `services/classification/`.**
   Files like `clients/minimax_client.py`, `services/classify_service.py`,
   and `services/draft_service.py` are aggressively single-line / compact;
   `clients/openai_client.py`, `clients/qdrant_client.py`, and
   `services/rag_service.py` follow PEP 257 multi-line rules. This is not
   a bug, but a reviewer skimming the code will read it as inconsistent
   quality. Action: normalize to either PEP 257 or to the repo's own
   single-line style consistently.

4. **`local_rag.py::DEFAULT_CONFIDENCE_THRESHOLD = 0.10` is hard-coded.**
   - The threshold is local to the in-process adapter and is not an
     operational knob. The hybrid lexical rerank already handles the
     "hash vector collides on unrelated queries" case structurally.
   - The README at line 246 says "Its default threshold is 0.28: if the
     highest score is below it (or the store is empty)…" but the code
     constant is 0.10. The 0.28 figure is left over from a prior
     commit and contradicts the current value.
   - **Fix**: either update the README to 0.10, or — better — make the
     threshold a keyword arg with a single canonical default and reference
     it from the README.

5. **`scripts/verify-baseline.sh` is a single-line wrapper.**
   ```sh
   set -eu
   python3 tests/test_noavia_workflow.py
   ```
   (4 lines total including the shebang). The README and `how-to-view-and-test.md`
   describe it as if it does more ("asserts Qdrant authentication/RBAC, that
   n8n has no Qdrant credential or URL, and the exact 10 MB Caddy rule for
   the NOAVIA webhook"). Those assertions are actually inside
   `tests/test_noavia_workflow.py` (header-auth assertion, the workflow
   JSON's headers, etc.). **Fix**: either (a) move those assertions into
   the shell script (with `grep -q` over `docker-compose.yml` and
   `Caddyfile`) or (b) correct the README to say the script delegates to
   the Python harness.

6. **Knowledge base is too small for a real demo.**
   - 8 files × 1 chunk each ≈ 8 chunks. The 40-case evaluation is calibrated
     against this exact corpus, so it works, but a real interview demo
     would benefit from a third obvious query type (e.g. "CSV import
     errors", "data retention policy", "priority/SLA") with maybe 2-3
     supporting chunks each. Adding ~3 more files (~600 bytes each) plus
     re-running the evaluator would push the corpus to a more believable
     size. Optional, but cheap.

### P2 — nice-to-have, not blocking

7. **No CI workflow** (`.github/workflows/`) is present. A reviewer
   expecting GitHub Actions for these tests would find none. The repo has
   only the local `scripts/test.sh`. Adding a single
   `.github/workflows/ci.yml` that runs `./scripts/test.sh` on every push
   and PR would round out the "reproducible delivery" claim.

8. **`noavia_kb_v1` collection name is referenced in evidence but never
   in code.** `evals/noavia_rag_eval.py` uses the local in-memory store
   and never references `noavia_kb_v1`; the live evidence says it was
   created with `AI_QDRANT_AUTH_ENABLED=false`. The mismatch is
   intentional (the live collection was created via direct Qdrant REST),
   but a reviewer will hunt for it. **Fix**: add a one-line note in
   `services/classification/README.md` "Ingestion" that the canonical
   production collection name is `noavia_kb_v1` (override `AI_RAG_COLLECTION`
   to match).

9. **Demo frontend does not print the exact fallback sentence** when no
   policy is matched. The workflow's `draft.grounded-reply.v1` produces
   the exact sentence "No specific policy found — this response is based
   on general knowledge." (`docs/decisions.md` calls this out as a
   transparency requirement), but the frontend's `demo_result()` hard-codes
   a different `"internal_draft_reply"` text. **Fix**: when the
   demo's classification maps to `manual_review`, emit the exact
   fallback sentence in the rendered demo. (Optional polish, but the
   transcript mentions the same fallback phrasing in two places.)

10. **`docs/decisions.md` lists 7 open items** (confidence threshold,
    PII/log retention, monitoring, cost caps, key rotation, model
    pinning, second-product reuse). All are documented as "not yet
    decided". Each is a real, named owner decision, not an implementation
    gap. **No fix needed** — these are correctly surfaced.

### Owner-only blockers (not implementation gaps)

These four items from `docs/noavia-final-report.md` §6 are owner-only by
project policy. They are not gaps in the repository; they are listed here
for completeness so the gap plan is one-stop.

- **Bind the Header Auth intake credential** in the isolated n8n instance.
- **Confirm the Google Sheets OAuth2 identity scope** (one test spreadsheet only).
- **Confirm the Gmail OAuth2 identity scope** (test/sink recipient only) and
  `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` mapping.
- **Authorize one live-integration test** and deactivate the workflow
  immediately after.

---

## 4. Recommended implementation sequence

The gap plan is small and each item is independent. The recommended order
respects the dependency graph (P0 fixes the doc, the type annotation, and
the ingest command — all prerequisites to any "interview-ready" claim).

| Step | Owner profile | Output | Verifies |
|---|---|---|---|
| 1. Fix `str *** None` → `str \| None` in `main.py` and `security.py` | coder (or python-engineer) | patch + add a regression test that imports the file without `from __future__ import annotations` | `pytest` still passes |
| 2. Fix `how-to-view-and-test.md` §B3 ingest command | documentation-agent | rewritten step that uses `ingest_cli.py` with a JSONL file (or calls `POST /internal/ingest/v1`) | manual review of the rewritten step |
| 3. Reconcile `local_rag.py` threshold and the README | coder + documentation-agent | either change code to 0.28 with a comment, or update README to 0.10 with a pointer to the constant | `python3 evals/noavia_rag_eval.py` reproduces committed JSON |
| 4. Either move shell assertions into `verify-baseline.sh` or correct the README | documentation-agent | single source of truth for "what this script does" | reading the script and the README agree |
| 5. Normalize docstring style in `services/classification/` | coder | consistent style across all files | `ruff`/`flake8-docstrings` clean |
| 6. Add `.github/workflows/ci.yml` running `./scripts/test.sh` | devops-engineer | CI badge, runs on push and PR | first green run on a branch |
| 7. Expand `knowledge-base/noavia/` from 8 to ~12 files | ragai-engineer | new fictional KB files + re-run evaluator | `noavia_rag_eval_results.json` regenerates; metrics not regressed |
| 8. Owner runs part B §B1–B4 (live integration) | owner only | n8n active execution, real Sheet row, real email | `docs/noavia-functional-verification.md` updated with dated record |

Steps 1–2 are ~30 minutes of work and gate the rest of the demo. 3–5 are
optional polish. 6–7 are nice-to-have. 8 is the actual end-to-end proof and
must be owner-run by project policy.

---

## 5. Work agents can proceed on autonomously (no blockers)

The following items from §3 are safe to assign to a worker without owner
approval:

- All of P0 items 1 and 2 (no credentials, no side effects, no
  external-service changes).
- P1 items 3, 4, 5 (style, docstring, doc-vs-script agreement).
- P2 items 6, 7, 8 (CI, threshold constant, KB expansion, demo
  fallback sentence).

Each can be done against the current working tree on a feature branch
without touching the owner's secrets, n8n, Qdrant, or the production
deployment. The audit found no items that require destructive changes,
shared history rewrites, or force-pushes.

---

## 6. Genuine blockers (require owner action)

These four are owner-only, listed here so the gap plan is exhaustive:

1. **Bind the Header Auth intake credential** in the isolated n8n
   instance (n8n direct binding, not a file edit).
2. **Confirm the Google Sheets OAuth2 identity scope** is restricted to
   the single test spreadsheet.
3. **Confirm the Gmail OAuth2 identity scope** and the
   `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` mapping.
4. **Authorize one live-integration test** with side effects, run it,
   then deactivate the workflow.

All four are listed in `docs/noavia-final-report.md` §6 and are
referenced from `docs/how-to-view-and-test.md` part B §B0–B4. They are
correctly framed as owner actions in every doc that mentions them.

---

## 7. What this audit explicitly did NOT do

To keep this audit honest:

- **No live HTTP call** to n8n, Qdrant, OpenAI, MiniMax, Google Sheets,
  Gmail, or any other external service.
- **No container started** — Docker / Compose are `Configured but
  unexecuted` in this audit.
- **No workflow imported** into n8n — the JSON was parsed and the
  Code-node logic was executed in a Node harness (the same one that
  `tests/test_noavia_workflow.py` uses), but the workflow itself was
  never activated in any n8n instance.
- **No secrets requested, retrieved, or stored** — no `.env` was read,
  no owner credential was supplied, no Paperclip secret was consulted.
- **No commits, pushes, or branch operations** were performed.
- **The classification test suite was not run end-to-end** in this audit
  session because the agent's Python 3.14 environment lacks the
  `qdrant_client` module. The previously recorded 39-of-39 pass
  (`docs/noavia-offline-delivery-evidence.md`) is referenced as canonical
  current state, not re-asserted as a new evidence record.

---

## 8. One-line per deliverable file

| File | Audit verdict |
|---|---|
| `README.md` | Crisp, accurate, points to the right docs. Skip the section "What's here" duplicates "Quickstart" — minor. |
| `AGENTS.md` | Untracked. Hermes board context, not a repo artifact. |
| `docker-compose.yml` | Verified. Network posture, fail-fast secrets, named volumes, health checks all correct. |
| `.env.example` | Verified. Names only, never values. |
| `.gitignore` | Verified. Covers `.env`, caches, data, volumes. |
| `Caddyfile` | Verified. 10 MB upload cap, conditional origin guard, localhost fallback prepared. |
| `docs/architecture-and-data-flow.md` | Verified. |
| `docs/capability-module-architecture.md` | Verified. Contract §3.1/§3.2/§3.3/§3.4 is the contract every other doc respects. |
| `docs/code-tour.md` | Verified. |
| `docs/decisions.md` | Verified. 7 open items honestly surfaced. |
| `docs/getting-started.md` | Verified. |
| `docs/how-to-view-and-test.md` | Has the §B3 ingest command defect (P0 #1). Otherwise verified. |
| `docs/n8n-paperclip-api-access.md` | Verified. |
| `docs/noavia-documentation-audit.md` | Verified. Six audit corrections all applied in current docs. |
| `docs/noavia-final-report.md` | Verified. |
| `docs/noavia-functional-verification.md` | Verified. |
| `docs/noavia-isolated-readiness-evidence.md` | Verified. |
| `docs/noavia-offline-delivery-evidence.md` | Verified. |
| `docs/noavia-rag-evaluation.md` | Verified. |
| `docs/recovery-manifest.md` | Verified. SHA-256 hashes line up with the current files I just read. |
| `docs/testing-guide.md` | Verified. |
| `evals/noavia_rag_eval.py` | Verified. SAI-52 median fix present. |
| `evals/noavia_rag_eval.jsonl` | Verified. 40 lines. |
| `evals/noavia_rag_eval_results.json` | Verified. Reproducible. |
| `knowledge-base/noavia/*.md` | Verified. 8 files, all <700 bytes, all fictional. |
| `knowledge-base/README.md` | Verified. |
| `scripts/test.sh` | Verified. |
| `scripts/verify-baseline.sh` | Misleading (P1 #5). |
| `services/classification/app/main.py` | Type annotation defect (P0 #2). Otherwise verified. |
| `services/classification/app/config.py` | Verified. |
| `services/classification/app/schemas.py` | Verified. |
| `services/classification/app/security.py` | Type annotation defect (P0 #2). Otherwise verified. |
| `services/classification/app/errors.py` | Verified. |
| `services/classification/app/logging_utils.py` | Verified. |
| `services/classification/app/ingest_cli.py` | Verified. |
| `services/classification/app/local_rag.py` | Verified locally; threshold constant reconcile with README (P1 #4). |
| `services/classification/app/clients/*` | Verified. |
| `services/classification/app/services/*` | Verified. |
| `services/classification/Dockerfile` | Verified. |
| `services/classification/requirements.txt` | Verified. |
| `services/classification/pytest.ini` | Verified. |
| `services/classification/README.md` | Verified. |
| `services/classification/tests/*` | Verified. 39 tests. |
| `services/frontend/app.py` | Verified. Server-side URL guard is solid. |
| `services/frontend/static/index.html` | Verified. |
| `services/frontend/Dockerfile` | Verified. |
| `services/frontend/requirements.txt` | Verified. |
| `services/frontend/tests/*` | Verified. |
| `tests/test_noavia_workflow.py` | Verified. |
| `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json` | Verified. 26 nodes, inactive, no literal secrets. |
| `workflow/noavia/README.md` | Verified. |

---

## 9. Bottom line

**The repository is interview-ready.** The architecture is sound, the
tests are honest, the secrets are absent, the docs distinguish verified
from unverified without overclaiming, and the owner-only blockers are
correctly framed as owner actions. The P0 gaps are a doc typo and a
latent type annotation defect — both small, both fixable in this session
if the user wants them fixed now, both safe to defer to a worker
otherwise.

The biggest interview risk is **not** a code defect; it is the
interviewer's experience if they try Part B §B3 and hit the bad ingest
command. Fix that one paragraph and the rest of the repo stands on its
own.
