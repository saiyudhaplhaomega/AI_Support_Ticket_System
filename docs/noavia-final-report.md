# NOAVIA — consolidated final report (SAI-27)

Compiled 2026-08-14 by the QA & Security Engineer as the independent review
required by SAI-27's acceptance criteria. This report consolidates evidence
already recorded in `docs/recovery-manifest.md`,
`docs/noavia-isolated-readiness-evidence.md`,
`docs/noavia-offline-delivery-evidence.md`, and
`docs/noavia-documentation-audit.md`; it does not re-run any live n8n or
Qdrant call (this session holds no `NOAVIA_N8N_API_KEY` or Qdrant credential)
and makes no claim beyond what those source records already establish.

## 1. GitHub / remote verification

- Canonical repository: `saiyudhaplhaomega/AI_Support_Ticket_System`.
- `origin/main` resolves to `83586bd371b530e6e63fe1677610d065b3991ddb`
  (`fix(noavia): correct RAG median bug and stale audit metric (SAI-52)`),
  confirmed via `git fetch origin main` in this review.
- Local `main` is one commit ahead (this report, `docs(noavia): add
  consolidated SAI-27 final report and QA review`). `git push origin main`
  fails in this runtime with "could not read Username for 'https://github.com'"
  — no GitHub push credential is available to this execution environment.
  This is a known, owner-acknowledged limitation (see accepted confirmation
  `2409c03f-24f6-4bfd-8278-6f9c476b4712`, 2026-08-14T00:48:59Z), not a new
  defect. The commit contains no code change — docs only — and is preserved
  in the canonical project workspace pending a push-capable run or an owner-
  supplied credential.
- Tracked-file secret scan (`sk-`, AWS `AKIA`, Slack `xox`, PEM private-key
  headers) over every `git ls-files` entry: no match. `.env` is not tracked
  and is git-ignored (`git check-ignore -v .env` confirms).

## 2. n8n workflow identity/state (isolated `paperclip-noavia` workspace)

Per `docs/noavia-isolated-readiness-evidence.md` (2026-08-14, control-plane
record, not reproduced live in this review session):

| Field | Value |
|---|---|
| Workflow ID | `udAuUv3ca0VPZdI8` |
| Name | `workflow.noavia-ticket-pipeline.v1` |
| Node count | 26 (matches the repository export) |
| Activation state | inactive |
| Webhook path | `noavia/tickets/v1` |

Discovery returned **exactly one** NOAVIA workflow — the duplicate-detection
requirement is satisfied. Node names/config match
`workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`; n8n's own
`webhookId` and empty `pinData` are non-executable metadata differences only.

Credential review of the tracked export (this session):

| Node | Credential type | Reference |
|---|---|---|
| `Ingest Support Ticket` | `httpHeaderAuth` | placeholder ID (`REPLACE_WITH_N8N_CREDENTIAL_ID`) — **not yet bound**, owner action required |
| `notify.google-sheets.v1` | `googleSheetsOAuth2Api` | credential ID reference only, no literal value |
| `initialize.google-sheets-header.v1` | `googleSheetsOAuth2Api` | same reference, node disabled |
| `notify.routing-email.v1` | `gmailOAuth2` | empty in the tracked export by design; the owner bound it directly in the isolated n8n instance only (not synced back to the repo, correctly) |

No credential value appears anywhere in the export. This matches
least-privilege expectations: the repository never carries a usable secret.

## 3. Qdrant / knowledge base

Per `docs/noavia-isolated-readiness-evidence.md`, live ingestion 2026-08-14:

- Endpoint: `http://qdrant:6333`, collection `noavia_kb_v1`, 256-dim cosine,
  `DeterministicHashEmbedder` (credential-free; OpenAI upgrade path documented
  as a remaining action, not yet applied).
- All 8 approved fictional knowledge-base files ingested, 1 chunk each, 8
  points total confirmed. Repository `knowledge-base/noavia/` currently
  contains exactly these 8 files (verified in this review): `api-token-rotation.md`,
  `csv-import.md`, `data-retention.md`, `duplicate-charge.md`,
  `email-notifications.md`, `knowledge-search.md`, `password-reset.md`,
  `priority-and-sla.md`.
- Duplicate-charge query top-3: `duplicate-charge.md` (0.255) ranked first,
  ahead of `csv-import.md` (0.056) and `knowledge-search.md` (0.055) —
  correct top-1 retrieval.
- Password-reset citation: `password-reset.md` top match, score 0.424.
- Low-confidence (astronomy/off-topic) probe: top score 0.143, above the
  0.10 collection-query threshold but marginal — recorded as an accepted
  limitation of the credential-free embedder, with an explicit note that
  production OpenAI embeddings should widen the separation. This is
  distinct from the workflow's own RAG fallback, which uses
  `config.rag_min_score` (default `0.6`) and is exercised offline in
  `tests/test_noavia_workflow.py`.
- No collection other than `noavia_kb_v1` was touched.

## 4. Tests — re-run in this review (2026-08-14)

```
$ python3 tests/test_noavia_workflow.py
PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present

$ ./scripts/test.sh
PASS: 26 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
services/frontend/tests/test_app.py ....                     [4 passed]
services/classification: 39 passed
  (test_api, test_config, test_errors, test_local_rag, test_qdrant_client,
   test_schemas, test_security)
node --test services/frontend/tests/browser.test.mjs          [2 passed]
```

All offline/credential-free suites pass, 45 tests total across the workflow
harness, classification service, and frontend, none requiring network or
secret access.

## 5. Requirement coverage (offline-verifiable set)

| Requirement | Status | Evidence |
|---|---|---|
| Intake validation (required fields, non-PDF/oversize attachment rejection) | Verified offline | `tests/test_noavia_workflow.py`, `Validate and Normalize` node |
| Strict classification JSON / service schemas | Verified offline | `services/classification` `test_schemas.py`, `test_api.py` |
| RAG top-3 retrieval, duplicate-charge ranking, citation sourcing | Verified offline (local hybrid) | §3 above, `evals/noavia_rag_eval_results.json` |
| Exact low-confidence fallback wording | Verified offline | harness checks the literal sentence `No specific policy found — this response is based on general knowledge.` |
| Confidence < 0.6 → manual-review override | Verified offline | harness cases at 0.44 and 0.59, including critical urgency |
| Urgency routing | Verified offline | harness billing/default-recipient cases |
| Google Sheets 16-column schema | Verified structurally | column list matches `docs/noavia-isolated-readiness-evidence.md` exactly |
| Structured/important-step logging | Verified structurally | correlation-ID propagation asserted in harness |
| PDF graceful fallback | Verified for Code-node behavior | invalid/oversize attachments rejected pre-processing; empty-extraction path retains ticket text |
| Bearer/header-auth rejection paths | Verified offline | `services/classification/tests/test_security.py` (missing/malformed/wrong-token all raise `AUTH_ERROR`/401) |
| Secrets never committed | Verified | §1 scan, `.env` git-ignored, all workflow credentials are ID references |
| Exactly one n8n workflow, inactive | Verified (control-plane record) | §2 |
| Qdrant: single dedicated collection, 8 sources ingested | Verified (control-plane record) | §3 |
| No email sent / no Sheet row written | Verified by absence | no execution evidence recorded anywhere in the repository; Gmail credential intentionally unbound in the tracked export |

## 6. Owner-action blocker checklist

These require the owner directly — no agent has secret access or the
authority to approve side effects:

1. **Bind the Header Auth intake credential** (`httpHeaderAuth` on
   `Ingest Support Ticket`) in the isolated n8n instance; the export
   deliberately ships a placeholder ID.
2. **Confirm scope of the existing Google Sheets OAuth2 identity** already
   selected on `notify.google-sheets.v1` / `initialize.google-sheets-header.v1`
   — restrict it to the intended test spreadsheet only.
3. **Confirm the Gmail identity bound in the isolated n8n instance** has
   access only to the approved test/sink recipient, and that
   `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` maps every route (including
   `default` and `manual_review`) to that single sink address.
4. **Explicit approval for one live-integration test**: activate the
   workflow only long enough to send one non-production ticket through the
   real webhook, then deactivate immediately. This is the only step that can
   write a Sheet row or send a Gmail message, and per the issue's hard
   boundary it must not run without this approval.

## 7. Exact credential setup — next actions

All names below already exist as documented, empty placeholders in
`.env.example`; none has a value in this repository or session.

**OpenAI** (optional production upgrade for embeddings/classification):
- Set `OPENAI_API_KEY` on the `services/classification` container only —
  never inject it into n8n.
- Set `AI_EMBEDDING_PROVIDER=openai` and `AI_EMBEDDING_MODEL=text-embedding-3-small`
  (already the `.env.example` default values).
- Re-run ingestion of `knowledge-base/noavia/` through the classification
  service so `noavia_kb_v1` is repopulated with real embeddings; the
  collection name and expected point count (8) do not change.

**Google Sheets**:
- Create/select a Google Sheets OAuth2 credential in the isolated n8n
  instance scoped to the single test spreadsheet
  (`NOAVIA_TEST_SHEET_NAME=NOAVIA Support Tickets - Test`).
- Bind that credential on both `notify.google-sheets.v1` and
  `initialize.google-sheets-header.v1` (already selected per §2 — confirm
  scope only, do not widen it).
- No `GOOGLE_SHEETS_CLIENT_ID` / `GOOGLE_SHEETS_CLIENT_SECRET` value should
  ever be committed; these stay in the n8n credential store or secret
  manager, never in `.env` tracked by git (it isn't).

**SMTP / email (Gmail node)**:
- This workflow uses an n8n Gmail OAuth2 node, not SMTP — there is no SMTP
  credential to configure.
- Bind a Gmail OAuth2 credential in the isolated n8n instance only, scoped to
  an identity that can send solely to the approved test/sink address.
- Set `NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` (server-side env var, not workflow
  input) so every category — including `default` and `manual_review` — maps
  to that one sink address. Never source the recipient from ticket fields
  (`requester_email`, `from_email`, etc.); the workflow already enforces
  this structurally.

## 8. QA & Security Engineer independent review — findings

Reviewed in this session: tracked workflow export, classification service
tests, `.env.example` contract, git history for prior QA corrections
(`docs/noavia-documentation-audit.md`), and the full offline test suite.

- **No blocking security/validation gap found.** Credentials are ID
  references only; the intake Header Auth credential is a placeholder by
  design, not an oversight; the Gmail credential is deliberately absent from
  the repo export and was bound only inside the isolated n8n instance.
- **Prior audit corrections verified as applied**: `workflow/noavia/README.md`
  correctly states the Gmail credential reference is empty in the tracked
  export (no longer claims a bound credential); the RAG evaluation
  median-bug fix (SAI-52) is present in `evals/noavia_rag_eval.py` and its
  regenerated results file is unchanged, confirming reproducibility.
- **All 45 offline tests pass** (26-node workflow harness + 4 frontend +
  39 classification + 2 browser), covering auth-rejection paths,
  low-confidence override, RAG fallback wording, and the Sheets schema.
- **No live-integration claim is overclaimed** anywhere in the docs
  reviewed: Sheets/Gmail bindings are consistently labeled configured-but-
  unexecuted, and no execution evidence exists in the repository.
- **Scope discipline held**: no evidence of any change outside the dedicated
  `paperclip-noavia` n8n workspace or the `noavia_kb_v1` Qdrant collection.

This review finds the repository and previously-recorded control-plane
evidence consistent, tested, and free of exposed secrets. The system is
complete for everything achievable without owner-held credentials/approval;
remaining work is the four owner actions in §6, which are genuine
first-party blockers, not implementation gaps.
