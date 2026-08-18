# Why we built it this way

> Historical platform note: these decisions record the retired
> Caddy/classification-service architecture. The current Part 1 architecture
> is documented in [current-architecture.md](current-architecture.md).

A decision log for the project owner: what was chosen, what the alternative
was, and why. Pair this with
[`docs/how-to-view-and-test.md`](how-to-view-and-test.md) (how to prove it
works) and [`docs/capability-module-architecture.md`](capability-module-architecture.md)
(the formal interface contract). Where a decision changed after a review
caught a problem, that's noted - this project's git history has several
real corrections, not just first drafts.

## Orchestration: n8n

**Chosen:** n8n as the workflow engine, one JSON export as the single
source of truth, imported inactive by default.

**Why:** the mission is a *reusable* SaaS factory - n8n gives a low-code,
visually inspectable pipeline that a non-engineer can open and follow, while
still allowing custom Code nodes for the parts (validation, routing math,
audit logging) that need precise, testable logic. The alternative - a
bespoke backend service - would be faster to unit-test but much harder to
hand over or modify without an engineer, which conflicts with the "handed
over" part of the mission.

**Trade-off accepted:** n8n's own execution behavior (activation, live HTTP
calls, credential resolution) can't be tested from a plain Python/Node test
runner - hence the two-tier testing approach in
[how-to-view-and-test.md](how-to-view-and-test.md): a credential-free harness
that parses the export and runs its Code-node logic directly (proves the
*logic*), separate from an owner-run live import (proves the *deployment*).

## Vector search: Qdrant, self-hosted

**Chosen:** Qdrant in its own container, JWT-scoped API key, RBAC enabled,
no default admin key handed to any application container.

**Why:** self-hosted keeps the knowledge base and its embeddings inside the
project's own infrastructure rather than a third-party SaaS vector store,
which matters for a support system that may eventually index real customer
policy/PII content. Qdrant specifically was picked over alternatives
(pgvector, Pinecone) for its collection-scoped access tokens - it's the one
that let us hand n8n *zero* Qdrant credentials at all (see next section)
while still letting the classification service read/write its one
collection.

## n8n never touches Qdrant or the model providers directly

**Chosen:** classification and RAG live in a standalone HTTP microservice
(`services/classification/`) that n8n calls over the internal Docker
network with a single bearer token. n8n holds no `OPENAI_API_KEY`, no
`MINIMAX_API_KEY`, and no Qdrant credential.

**Why:** this was an explicitly resolved open question (architecture doc
§7 - "n8n sub-workflow vs. standalone service?"). A standalone service won
because it (a) is independently unit-testable without a running n8n
instance - which is most of why Part A of the testing guide is possible at
all - and (b) is reusable by any future non-n8n product without
duplicating the RAG logic, matching the "reusable capability modules"
mission statement directly. The cost is one more container to deploy and
one more internal API contract to keep stable, which is why that contract
is pinned in `services/classification/README.md` as a versioned interface
(`ai.classify-ticket.v1`, `ai.rag-lookup.v1`).

## Model split: OpenAI for embeddings, MiniMax for chat

**Chosen:** `text-embedding-3-small` (OpenAI) for RAG embeddings;
`MiniMax-M3` for the two chat calls (classification JSON, drafted reply).

**Why:** embeddings are called on every knowledge-base ingest and every
ticket lookup, and OpenAI's small embedding model is inexpensive and
well-established for retrieval quality. The two chat calls are the more
expensive part of the pipeline per ticket, so MiniMax was substituted there
specifically to cut operating cost without touching the embedding/retrieval
quality path. Both providers are configured independently
(`AI_EMBEDDING_PROVIDER` / `AI_CHAT_PROVIDER` in `.env.example`) so either
side can be swapped back without touching the other.

## Reverse proxy: Caddy, single public entry point

**Chosen:** Caddy in front of everything, automatic HTTPS, and it is the
*only* container that publishes a host port. Qdrant, the classification
service, and n8n itself are reachable only by container DNS name on the
internal Docker network.

**Why:** the default posture is "internal-only unless someone deliberately
adds a route" - this makes accidental exposure structurally hard rather
than something that has to be remembered. Caddy specifically over
nginx/Traefik for automatic certificate provisioning/renewal with minimal
config, since this stack is meant to be stood up by future non-infra
engineers reusing the same Compose file for other products.

## Confidence threshold and routing tiers

**Chosen:** `confidence < 0.6` forces `status = needs-manual-review`
*regardless of urgency* (a critical-urgency, low-confidence ticket still
gets flagged for a human); urgency then drives notification breadth
(critical/high → full email + Sheets row, medium → brief email + Sheets
row, low → Sheets only).

**Why:** the two axes answer different questions - confidence is "should a
human sanity-check the AI's read of this ticket," urgency is "how loudly
should we alert someone." Conflating them (e.g., only checking confidence
for high-urgency tickets) would let a low-confidence but low-urgency ticket
silently auto-route with no human check, which is the failure mode this
threshold exists to prevent. `0.6` is a starting value, not a tuned one -
see [Open items](#open-items-and-things-to-revisit) below.

## The exact fallback sentence

**Chosen:** when RAG retrieval falls below `config.rag_min_score` (default
0.6), the draft reply must contain the literal sentence *"No specific
policy found - this response is based on general knowledge."*

**Why:** this is a transparency requirement, not a formatting nicety - a
customer-facing draft that sounds authoritative but isn't grounded in an
actual policy document needs to say so, verbatim and predictably enough
that it can be asserted on in a test rather than eyeballed. That's why the
offline harness checks for the exact string rather than "some disclaimer is
present."

## Test-mode frontend as a safety boundary, not just a demo

**Chosen:** the demo form defaults to `NOAVIA_TEST_MODE=true`, which never
contacts n8n at all - a real webhook URL is only reachable if an owner
explicitly disables test mode, and even then the URL is validated
server-side (no credentials/IPs/query strings/fragments allowed in it) and
never shipped to browser code.

**Why:** the risk being designed against is a demo build accidentally
becoming a live ticket-submission path - either by leaking a real webhook
URL into client-side JS, or by someone flipping a flag without realizing
what it enables. Making test mode the *default* and the real path require
explicit, validated, server-only configuration means the safe state is also
the easy state.

## Why agents never hold production credentials

**Chosen:** no agent working on this project - CEO, Codex implementers, the
Documentation Agent - is given `OPENAI_API_KEY`, Google/Gmail OAuth, or a
broad n8n admin key. Where an agent needs *any* n8n access at all (e.g. to
read the workflow ID and confirm no duplicate exists), it's scoped per
a scoped, approval-gated API access runbook for
dedicated, isolated identity/project with the minimum API scopes for a
specific stage, approved by the owner first.

**Why:** the operating rules for this project are explicit that deployment,
credential, and side-effect decisions require owner approval - and
practically, it means every "verified" claim in this repo's docs is backed
by evidence an agent could actually produce (parsing an export, running a
mocked test) rather than a claim that would require trusting an agent with
a real inbox or a real customer spreadsheet. This is also why Part B of the
testing guide is something the owner runs, not something an agent claims to
have already done on the owner's behalf. As a consequence, each isolated
implementation task is independently reviewed before its branch is
integrated into the main tree.

## Why there are two separate test tiers instead of one

**Chosen:** offline/credential-free tests (45 of them, run by any agent, no
network) are kept structurally separate from any live-integration claim.

**Why:** the project's own history has a real example of why this
separation matters - the RAG evaluation script had a median-calculation bug
that inflated a reported accuracy number, caught and fixed in SAI-52. A
single blended "it works" test suite that mixes offline logic checks with
unverifiable live claims makes that kind of bug harder to catch, because a
reviewer can't tell which numbers came from a deterministic assertion and
which came from a network call nobody can re-run without secrets. Keeping
them apart means every claim in this repo says exactly what kind of
evidence backs it (see the "Verified offline" / "Configured but unexecuted"
labels used throughout `docs/`).

## Open items and things to revisit

Not yet decided, or decided as a placeholder pending real usage data:

- **Confidence threshold (0.6) and RAG score threshold (0.6)** are starting
  values, not tuned against real ticket volume - revisit once real tickets
  flow through and manual-review rate can be measured.
- **PII/log retention** is explicitly called out as unset in the delivery
  checklist (`docs/noavia-offline-delivery-evidence.md`) - needs an owner
  decision on how long ticket text, AI summaries, and processing logs are
  kept before this goes anywhere near real customer data.
- **Monitoring/alerting** on the live stack (container health, failed
  executions, delivery failures) isn't built yet - currently you'd only
  notice a failure by checking n8n's Executions list manually.
- **Cost caps** on AI provider spend aren't enforced anywhere in the stack;
  a spike in ticket volume currently has no circuit breaker.
- **Key rotation** cadence for the Qdrant JWT, classification service
  bearer token, and OAuth credentials isn't scheduled - currently
  ad hoc/manual.
- **Model version pinning** - `MiniMax-M3` and `text-embedding-3-small` are
  referenced by name; if either provider deprecates or silently updates
  behind that name, nothing in this stack detects a quality regression
  except rerunning `evals/noavia_rag_eval.py` by hand.
- **Reuse for a second product**: the capability-module contract
  (`docs/capability-module-architecture.md`) is designed to make this
  possible, but hasn't actually been exercised by a second consumer yet -
  worth treating the first reuse attempt as a test of the contract itself.

## Known debt (designed + ticketed, per FINAL PLAN v6 §2.5)

These items are intentionally NOT closed in the 2026-08-16 readiness round.
Each is sized, designed at a paragraph level, and tracked as a separate
ticket so a future round can pick it up with full context. None of them
are hidden risk; all of them are listed because a sharp interviewer would
ask "why isn't this here?" and these are the honest answers.

- **T1 (NOAVIA-S1): split the shared bearer into two symmetric tokens.**
  Today the classification service holds one bearer; the same secret
  authenticates both `/ai/classify-ticket|/ai/rag-lookup|/ai/grounded-draft`
  (read) and `/internal/ingest/v1` (write). Splitting it into
  `AI_CLASSIFY_API_KEY` (read) and `AI_INGEST_API_KEY` (write) is the
  minimum a production-bound deployment needs; until then, a leaked
  read-key can also write. Half a day. Owner-approval gate.
- **T2 (NOAVIA-S2): mitigate prompt injection in email summary.** The
  surface is `services/classification/app/services/draft_service.py`, NOT
  the workflow's `draft.grounded-reply.v1` (the latter is a pure Code
  node with no model call). Three options, in order of fidelity:
  (a) structured-output-only chat call where the email body is composed
  from structured fields plus citation metadata and customer text never
  appears verbatim; (b) pre-summarize customer text via a separate
  non-prompt-injection call and feed only the summary into the draft
  prompt; (c) truncate the ticket body to a 200-char prefix in the draft
  prompt and template the email body from classification + RAG hits
  (lowest fidelity). C1's executionRetention is defense-in-depth only;
  T2 is the authoritative PII / prompt-injection fix.
- **T3 (NOAVIA-S3): webhook idempotency.** No persistent store is
  available in n8n today, so a duplicate webhook delivery will produce
  duplicate audit logs (and possibly duplicate Sheet rows if the
  delivery path retries). Two options: (a) add a small Redis container
  to docker-compose as the dedup store (durable, adds infra);
  (b) accept + document the duplicate-audit-logs limitation honestly
  and defer until V2. DEFAULT: option (b). Owner may pick (a) at
  planning time.
  `N8N_API_KEY` is NOT being rotated or replaced in this readiness round
  per owner instruction.
