# NOAVIA isolated readiness evidence

Status: partially live-validated, with external integrations deliberately
unconfigured. This is a control-plane and local-fixture record, not a claim
that Google Sheets, SMTP, OpenAI, or production Qdrant ingestion was tested.

## Isolated n8n workspace — 2026-08-14

The dedicated `paperclip-noavia` API capability was used only against the
internal n8n endpoint. Workflow discovery returned exactly one workflow:

| Field | Observed value |
| --- | --- |
| ID | `udAuUv3ca0VPZdI8` |
| Name | `workflow.noavia-ticket-pipeline.v1` |
| Nodes | 24 |
| Activation state | inactive |
| Webhook path | `noavia/tickets/v1` |

The imported workflow has the same node names and executable node
configuration as `workflow/noavia/workflow.noavia-ticket-pipeline.v1.json`.
n8n assigned its own `webhookId`; its empty `pinData` representation differs
from the export, which is non-executable metadata. No activation or execution
was attempted: the three delivery credentials remain placeholders and a live
run could write a Sheet row or send email.

## Qdrant / knowledge-base — live ingestion 2026-08-14

Qdrant confirmed reachable at `http://qdrant:6333` (unauthenticated,
`AI_QDRANT_AUTH_ENABLED=false` per owner approval). Collection `noavia_kb_v1`
created with 256-dimensional cosine vectors using `DeterministicHashEmbedder`
(credential-free; production upgrade path is to swap in the OpenAI adapter).

All eight fictional Markdown sources ingested directly via Qdrant REST API:

| # | File | Chunks |
|---|------|--------|
| 1 | api-token-rotation.md | 1 |
| 2 | csv-import.md | 1 |
| 3 | data-retention.md | 1 |
| 4 | duplicate-charge.md | 1 |
| 5 | email-notifications.md | 1 |
| 6 | knowledge-search.md | 1 |
| 7 | password-reset.md | 1 |
| 8 | priority-and-sla.md | 1 |

**Total: 8 points confirmed in collection.**

**Duplicate-charge top-3 retrieval:**
1. `knowledge-base/noavia/duplicate-charge.md#0` (score=0.255)
2. `knowledge-base/noavia/csv-import.md#0` (score=0.056)
3. `knowledge-base/noavia/knowledge-search.md#0` (score=0.055)
— low_confidence=False (duplicate-charge correctly ranked first)

**Password-reset citation:**
- source=`knowledge-base/noavia/password-reset.md` score=0.424 (top match)

**Low-confidence / astronomy (unrelated) query:**
- Top match score=0.143 (above threshold=0.10); retrieval returns results but
  confidence is marginal. Production threshold can be tuned after live
  OpenAI embeddings improve separation.

## Tests executed

```text
python3 tests/test_noavia_workflow.py
PASS: 24 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present

./scripts/verify-baseline.sh
PASS: 24 nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present
```

## Remaining owner / platform actions

1. **GitHub remote publication**: Required before release. `origin/main` is
   currently `7059d3bf42f8659cb9c4641f04029706f8e77ad1`; local commit
   `60a60ea` (`fix: minimize noavia secret exposure`) is reviewed but has not
   been published because this runtime has no GitHub authentication. An owner
   or CI identity with repository push permission must push `60a60ea` to
   `origin/main`, then verify `git rev-parse HEAD` and
   `git rev-parse origin/main` resolve to the same SHA. Do not treat the
   security-hardening change as remotely verified until then.
2. **OpenAI upgrade** (optional for production): Replace `DeterministicHashEmbedder`
   with OpenAI `text-embedding-3-small` by injecting `OPENAI_API_KEY` into
   the classification service only (do not inject it into n8n). Re-ingest `knowledge-base/noavia` via the service
   to get production-quality embeddings. The collection name `noavia_kb_v1` and
   point count remain the same.
3. **n8n credentials**: In n8n workspace, replace the three credential placeholders
   with: Header Auth for webhook intake, least-privilege Google Sheets OAuth2
   access to the intended test spreadsheet/tab, and SMTP access restricted to
   the approved sender. Supply `config.rag_collection = noavia_kb_v1`.
4. **Live integration test** (owner approval required): With explicit approval
   for side effects, activate and test using a non-production Sheet and SMTP
   sink, then deactivate immediately after.

No credential value is included in this record.
