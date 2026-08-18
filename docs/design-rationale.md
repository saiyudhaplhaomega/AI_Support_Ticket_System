# Design rationale

The four questions every reviewer asks: what was decided, how AI output is validated,
how RAG is set up, and what would come next. The [root README](../README.md) carries a
condensed version of this under "Design notes". This page is the longer form.

## Key architecture decisions

**Native n8n nodes over a custom microservice.** An earlier iteration ran
classification behind a FastAPI service. It was removed. Everything the task needs
is expressible in native nodes, and a custom API layer added a deployment surface,
an auth boundary and a second failure domain without earning any of them. The
pipeline is now Webhook → validate → optional PDF extraction → classify → retrieve →
draft → route → Sheets/Gmail → respond.

**Two workflows, not one.** Knowledge ingestion is a separate manual-trigger workflow
so the collection can be rebuilt without touching the ticket path, and so a re-index
is never a side effect of a customer ticket.

**The draft is never sent.** `notify.routing-email.v1` targets an internal
server-side recipient allow-list (`NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON`), never an
address taken from ticket input. The generated reply is stored and emailed to staff
only.

**Failures degrade, they do not drop tickets.** Every external call -
Drive, PDF extraction, Qdrant, both OpenAI steps, Sheets, Gmail - runs with
`onError: continueRegularOutput`. A ticket with a corrupt PDF, a dead vector store
or a failed classifier still reaches Google Sheets with a populated
`processing_log`. Losing a customer ticket is worse than storing a degraded one.

## How I handle AI output validation, and why

Four layers, because each catches something the others cannot:

1. **Transport** - HTTP status and `error` field checked before parsing.
2. **Shape** - the model is asked for JSON, but `response_format: json_object` is
   *silently dropped* by n8n's native OpenAI node, which forwards only model,
   messages, temperature and maxTokens. I confirmed this against live executions, so
   the parser strips markdown fences before `JSON.parse` rather than trusting JSON mode.
3. **Schema** - `category`, `urgency` and `sentiment` are checked against
   allow-lists; `confidence` must be a finite number in [0,1]; `summary` must be a
   non-empty string. Anything else throws.
4. **Semantic** - `confidence < 0.6` forces `status = needs-manual-review`
   regardless of urgency.

Why this shape: an LLM failure should never look like a success. Any breach routes to
`Classification Fallback`, which emits a valid ticket marked for manual review with
the error preserved, so the pipeline is fail-safe rather than fail-open. Enum
membership is checked rather than coerced, because a silently coerced category is a
wrong answer that looks like a right one.

**Deliberate deviation:** urgency is not purely the model's call. A code-level floor
raises urgency when the customer explicitly signals it or attaches a document, because
in testing a ticket reading "urgent" with a real problem attached was graded `low` and
sent no notification. The floor only raises, never lowers, never reaches `critical`,
and reads only customer-authored `subject`/`body` - never extracted PDF text, so a
crafted attachment cannot escalate its own ticket. The model's original value is kept
in `urgency_model` alongside `urgency_source` for auditability.

## RAG implementation

**Knowledge base** - 9 markdown documents covering support policy, billing, account
and product topics.

**Chunking** - recursive character splitter, 800 characters with 120 overlap, using
the markdown separator set so splits prefer heading and paragraph boundaries. 800 is
large enough to keep a complete policy statement intact and small enough that three
chunks fit the draft prompt without crowding out the ticket. The 15% overlap stops a
policy sentence spanning a boundary from being lost to both neighbours.

**Embedding model** - `text-embedding-3-small`, 1536 dimensions, explicitly pinned on
*both* the ingestion and retrieval nodes. Chosen over `-3-large` because at this
corpus size the retrieval quality difference is not measurable while cost is ~6.5×
lower, and over a local model because the pipeline already depends on OpenAI, so
adding a second embedding runtime buys nothing here. Pinning the dimension on both
sides is deliberate: a silent dimension mismatch between ingestion and query is the
single most common way a RAG pipeline returns confident nonsense.

**Retrieval** - native Qdrant vector store node, `top_k = 3`, cosine similarity over
collection `noavia_kb_v1`, with a `rag_min_score` threshold applied in code after
retrieval. The threshold is 0.1, which looks low and is not arbitrary: measured
against `evals/`, supported queries score 0.14–0.50 while unsupported queries score 0,
so 0.1 sits in the gap. When nothing clears it, the draft prompt is instructed to
include exactly: *No specific policy found - this response is based on general
knowledge.* Source filenames are carried through as citations; the email lists only
the sources the draft actually cited, while the Sheets row keeps all retrieved
sources for audit.

## What I would improve with more time

1. **Automated retrieval evaluation in CI.** `evals/` calibrated the threshold once,
   manually. It should be a golden set of question/expected-source pairs producing
   recall@3 and MRR on every KB change, so re-chunking cannot silently regress
   retrieval.
2. **A reranker.** Retrieval currently trusts raw cosine similarity. A cross-encoder
   over the top ~10 before selecting 3 would cut the marginally-related third source.
3. **Groundedness checking.** Nothing verifies the draft's claims are actually
   supported by the retrieved chunks. A claim-level entailment check should gate
   drafts before staff review.
4. **Idempotent re-ingestion.** Ingestion inserts; it does not upsert by source hash,
   so a re-run duplicates chunks. Delete-by-source-then-insert, keyed on a content
   hash, would make it safely repeatable.
5. **Structured outputs properly.** Since the native node drops `response_format`, the
   proper fix is a direct HTTP call with strict JSON schema, or n8n's Structured
   Output Parser, rather than defensive fence-stripping.
6. **Retry with backoff** on the two OpenAI calls. A transient 429 currently
   goes straight to manual review, which is correct but wasteful.
7. **Load and cost behaviour.** No testing has been done on concurrent webhook
   traffic, and there is no per-ticket token budget or spend cap.
