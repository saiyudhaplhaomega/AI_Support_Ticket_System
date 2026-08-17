# NOAVIA Part 1 — README

## Key architecture decisions

**Classification/drafting is a dedicated Python HTTP service**
(`services/classification/`), called over an authenticated contract
(`ai.classify-ticket.v1`). This keeps prompt construction and JSON-schema
validation in testable, versioned code instead of buried in Code-node
strings, and lets the service be reused by future workflows. **RAG
retrieval, by contrast, uses n8n's native Qdrant Vector Store node
directly** — a plain similarity search against a fixed collection doesn't
need custom service code, and it's one fewer moving part (no HTTP
round-trip, no service-side embedding call to duplicate) for something
n8n already does natively. Ingestion (chunking the KB into Qdrant) uses
the same native nodes. Rule of thumb applied here: reach for a custom
service when the AI call needs project-specific structured-output
validation (classification); use n8n's built-in nodes when the operation
is a standard, parameterized one (vector search).

**Every external call — classify, RAG lookup, Sheets, email — follows the
same pattern: try → branch on ok/error → log either way → never let one
failure kill the whole ticket, but always leave a status/error trail on the
Sheet row.** A classification failure stubs `category: manual_review,
confidence: 0` and continues; a RAG failure continues with an empty match
list; a Sheets/email failure still returns a `502 DELIVERY_ERROR` envelope
instead of hanging. Nothing hard-fails; everything degrades with a visible
trail.

**Provider:** OpenAI end to end — `text-embedding-3-small` for embeddings,
`gpt-4o-mini` for classification/drafting. Started with MiniMax-M3 for
chat (cheaper per call), but its variable reasoning-model latency (4.5s
to 25s+ observed) made it a poor fit for a synchronous webhook response;
switched to a non-reasoning OpenAI model, which is both faster and more
predictable. The provider is swappable via `AI_CHAT_PROVIDER`/
`AI_CHAT_MODEL` — the MiniMax path is still implemented and tested,
just not the default.

**Routing recipients are server-side-only**, read from an env-var
allow-list (`category → email`) — never derived from ticket fields. A
crafted `requester_email` or custom field can never redirect a
notification.

## AI output validation

Both AI endpoints require `response_format: json_object` from the model,
and the service additionally validates the parsed JSON against a strict
Pydantic schema (`category`, `confidence ∈ [0,1]`, `urgency`, `sentiment`,
`summary`, `tags`) before anything downstream sees it. Anything that fails
to parse or fails schema validation raises a typed error and n8n's `IF`
node routes it to the fallback branch — never a partially-formed value into
the Sheet or an email.

On top of that, **confidence < 0.6 always forces `category: manual_review`
and `status: needs-manual-review`**, regardless of what the model returned
— a self-reported confidence score isn't fully trustworthy on its own, but
it's a cheap, useful gate.

One real bug this validation caught during the build: `MiniMax-M3` is a
reasoning model that wraps its answer in a `<think>...</think>` block plus
a markdown-fenced JSON object, even with `response_format=json_object`
set — so naive `json.loads(content)` silently failed on every call. Fixed
by stripping the think-block and extracting the JSON object before
parsing. It's a concrete example of why `response_format` alone isn't a
guarantee and schema validation with a fallback branch (not a crash) is
load-bearing.

## RAG implementation

**Knowledge base:** 8 short, self-contained markdown policy docs (password
reset, duplicate charges, priority/SLA, data retention, CSV import, API
token rotation, email notifications, knowledge search).

**Chunking:** one Qdrant point per document (whole-file chunking), not
sub-document splitting. Each doc is already a single short, single-topic
policy — splitting would fragment one coherent answer across multiple
retrieved chunks for no benefit at this KB size. At a larger KB I'd switch
to heading/section-based chunking with overlap.

**Embedding model:** OpenAI `text-embedding-3-small` (1536-dim), same
model for ingestion and query time — required for cosine similarity to be
meaningful. The "small" variant is enough for a handful of internal
policy docs; no need for frontier retrieval quality here.

**Retrieval:** top-3 cosine similarity search against a fixed Qdrant
collection, via n8n's native Qdrant Vector Store node (`load` mode) with
an Embeddings OpenAI subnode for the query vector — same collection and
embedding model the ingestion workflow uses. Matches below `rag_min_score`
(default 0.6) are dropped even if they placed in the top 3; if that
leaves zero usable matches, the draft falls back to the literal required
string ("No specific policy found — this response is based on general
knowledge.") instead of inventing an answer. Matches that clear the
threshold are cited by source document and similarity score in the
drafted reply.

## What I'd improve with more time

- Heading/section-aware chunking with overlap once the KB outgrows a
  handful of single-topic files.
- A retrieval eval set (query → expected source doc) to track recall/
  precision over time instead of spot-checking individual tickets.
- Surface the actual upstream error detail (not just a generic
  `UPSTREAM_ERROR` code) in the Sheet row — diagnosing the MiniMax
  parsing bug above took real time that better error surfacing in the
  row itself would have saved.
- Hybrid (keyword + vector) search or reranking once the KB is large
  enough that pure cosine similarity starts missing exact-term matches
  (error codes, SKUs, ticket IDs).
