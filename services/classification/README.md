# ai.classify-ticket.v1 / ai.rag-lookup.v1 - classification & RAG service

Owner: RAG & AI Integration Engineer. Standalone HTTP service implementing
the two `ai.*` interfaces defined in
[`capability-module-architecture.md`](../../../capability-module-architecture.md)
§3.1/§3.2. Product-agnostic - NOAVIA is the first consumer, not the only one.
Consumers (n8n or otherwise) only need this document; nothing below the
"Endpoints" section is required reading to integrate.

**§7 open question resolved:** this ships as a standalone HTTP service (not
an n8n sub-workflow), so any future product - n8n-based or not - can call it
the same way.

## Running it

```sh
cd infra
cp .env.example .env   # fill in OPENAI_API_KEY, MINIMAX_API_KEY, AI_CLASSIFY_API_KEY at minimum
docker compose --profile classification-service up -d --build
```

Reachable at `http://classification-service:8080` from any container on the
`saas-internal` network (e.g. n8n's HTTP Request node). Not published to a
host port and not routed through Caddy - internal-only, like Qdrant.

## Auth

Every endpoint below except `/healthz`/`/readyz` requires:

```
Authorization: Bearer <AI_CLASSIFY_API_KEY>
```

using the same `AI_CLASSIFY_API_KEY` value Infra already provisions in
`.env`/the secret store (see `infra/.env.example`). Missing/invalid token →
`401` with `error.code = "AUTH_ERROR"`.

## Endpoints

### `POST /ai/classify-ticket/v1`

Request:

```json
{
  "text": "I was charged twice for my subscription this month",
  "context": { "categories": ["billing", "technical", "account", "other"] },
  "locale": "en-US"
}
```

- `text` (required) - ticket body.
- `context` (optional) - `context.categories: string[]` overrides the
  default taxonomy (`AI_CLASSIFY_CATEGORIES_DEFAULT`) for this call; any
  other keys are passed to the model as extra context, not interpreted.
- `locale` (optional).

Success response (`200`):

```json
{
  "ok": true,
  "data": {
    "category": "billing",
    "confidence": 0.92,
    "tags": ["duplicate_charge", "refund"],
    "urgency": "medium",
    "sentiment": "negative",
    "summary": "Customer reports a duplicate subscription charge.",
    "raw_model_output": { "provider": "minimax", "model": "MiniMax-M3", "id": "...", "usage": {...} }
  }
}
```

`category`, `confidence`, and `tags` are the original published v1 fields
(`capability-module-architecture.md` §3.1) and are always required -
consumers built against the original contract keep working unchanged.
`urgency`, `sentiment`, and `summary` are additive optional fields (§4 -
"additive optional fields do not require a bump") added when chat moved to
MiniMax; the service fills them on every call, but they should be treated as
optional, not required. All six fields are validated from MiniMax JSON chat
output. Invalid or non-JSON model output returns the standard error
envelope; downstream automation never parses free text. `confidence` is the
model's self-reported estimate (0-1); treat it as a routing heuristic, not a
calibrated probability.

### `POST /ai/grounded-draft/v1`

Creates a concise support reply using at most three supplied RAG matches. The
service preserves source metadata as citations and sends the chat request to
MiniMax, never OpenAI. With no retained matches it returns exactly
`No specific policy found — this response is based on general knowledge.` and
an empty citation list.

```json
{
  "ticket_text": "I was charged twice for my subscription this month",
  "matches": [{ "id": "kb-42", "score": 0.87, "content": "...", "metadata": { "source": "policies/refunds.md" } }]
}
```

### `POST /ai/rag-lookup/v1`

Request:

```json
{
  "query": "how do I reset my password",
  "top_k": 5,
  "filter": { "must": [{ "key": "source", "match": { "value": "kb" } }] },
  "collection": "kb_documents"
}
```

- `query` (required).
- `top_k` (optional, default `AI_RAG_TOP_K_DEFAULT`, capped at `AI_RAG_TOP_K_MAX`).
- `filter` (optional) - a [Qdrant filter](https://qdrant.tech/documentation/concepts/filtering/) object, passed through as-is.
- `collection` (optional, **additive field, not in the original v1 spec's
  required set** - additive optional fields don't require a version bump per
  architecture doc §4). Defaults to `AI_RAG_COLLECTION` so single-collection
  products never need to pass it.

Success response (`200`):

```json
{ "ok": true, "data": { "matches": [ { "id": "...", "score": 0.87, "content": "...", "metadata": { "source": "kb" } } ] } }
```

Querying a collection that doesn't exist yet returns `matches: []`, not an
error - lets a new product call this before its first ingest run.

### `POST /internal/ingest/v1` (operational, not a published `family.module` interface)

Populates the collection `rag-lookup` reads from. Not versioned like the two
interfaces above - it's implementation detail of how this module keeps its
own data store current, documented here for whoever operates ingestion
(n8n workflow, cron, manual script), not a cross-team contract.

```json
{
  "collection": "kb_documents",
  "records": [
    { "id": "kb-42", "content": "How to reset your password: ...", "metadata": { "source": "kb", "url": "..." } }
  ]
}
```

`id` is optional (a stable id is derived from content if omitted); re-ingesting
the same `id`/content upserts in place rather than duplicating. `records` is
capped at 500 per call - batch larger loads across multiple calls, or use
the CLI below.

For bulk/offline loads, use the CLI instead of the HTTP endpoint:

```sh
python -m app.ingest_cli --file kb.jsonl --collection kb_documents
```

where `kb.jsonl` is one JSON object per line matching the `records` item
shape above. The CLI reads the same env vars as the service.

### `GET /healthz` / `GET /readyz`

`/healthz` - liveness, no auth, no upstream calls (used by the Docker
healthcheck). `/readyz` - readiness, pings Qdrant; `503` if unreachable.

## Error envelope

Every non-success response - validation, upstream timeout/failure, auth,
internal - uses the shared envelope from architecture doc §5:

```json
{ "ok": false, "error": { "code": "UPSTREAM_TIMEOUT", "message": "...", "interface_id": "ai.classify-ticket", "version": "v1", "correlation_id": "..." } }
```

**HTTP status codes**: `AUTH_ERROR` responses use `401` (a transport/security
gate, not a business-logic outcome). Every other error code (`VALIDATION_ERROR`,
`UPSTREAM_TIMEOUT`, `UPSTREAM_ERROR`, `INTERNAL_ERROR`) is returned with HTTP
`200` - per the architecture doc's SLA note, these must come back as a
parseable envelope so the n8n caller can branch on `ok` and route to a
fallback/manual queue, without needing "continue on fail" node config to
avoid a hard failure on expected error paths. **Always check `data.ok`
first; the HTTP status alone is not sufficient to tell success from a
handled business-logic error.**

`correlation_id`: pass `X-Correlation-Id` (generated once at workflow
ingestion, per qa.validation-and-logging.v1 §3.4) and it's threaded through
this service's logs and echoed back in the response header/error envelope.
If omitted, one is generated per-request.

## Env vars

Secrets (required, service refuses to start without them - see
`app/config.py`): `OPENAI_API_KEY`, `MINIMAX_API_KEY`, `AI_CLASSIFY_API_KEY`,
and `QDRANT_URL`. OpenAI is used only for embeddings; MiniMax is used only for
classification and grounded drafting. The explicit, validated defaults are
`AI_EMBEDDING_PROVIDER=openai`,
`AI_EMBEDDING_MODEL=text-embedding-3-small`, `AI_CHAT_PROVIDER=minimax`, and
`AI_CHAT_MODEL=MiniMax-M3`.
`AI_QDRANT_AUTH_ENABLED` defaults to `true`; in this mode
`AI_QDRANT_API_KEY` is required and must be a short-lived, collection-scoped
Qdrant JWT (`rw` for collections this service ingests into; `r` for query-only
deployments). For a Qdrant deployment configured without authentication, set
`AI_QDRANT_AUTH_ENABLED=false` and omit `AI_QDRANT_API_KEY`. The service then
creates its client without a key. The Qdrant admin/signing key is never supplied
to this service. Do not set the flag to false merely to work around a missing
credential on an authenticated deployment.

Everything else is optional with a built-in default - see
`infra/.env.example` for the full list (`AI_EMBEDDING_MODEL`, `AI_CHAT_MODEL`,
`AI_RAG_COLLECTION`, `AI_CLASSIFY_CATEGORIES_DEFAULT`, etc.). Future products
override only what they need; nothing here is NOAVIA-specific.

## Local dev

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
OPENAI_API_KEY=dev-openai-key MINIMAX_API_KEY=dev-minimax-key AI_CLASSIFY_API_KEY=dev-secret QDRANT_URL=http://localhost:6333 \
  AI_QDRANT_AUTH_ENABLED=false \
  uvicorn app.main:app --reload --port 8080
```

Tests mock the OpenAI embeddings, MiniMax chat, and Qdrant clients - no
network calls or real keys are needed:

```sh
pip install -r requirements-dev.txt
pytest -q
```

## Deterministic local RAG path

For local fixtures and contract testing, `app.local_rag` offers a standalone
credential-free adapter. It deliberately does not call the HTTP service,
OpenAI, or Qdrant. `DeterministicHashEmbedder` uses a stable BLAKE2b signed
hash embedding and `InMemoryVectorStore` provides deterministic upsert/search.
Hosted adapters may replace either behind the `Embedder` and `VectorStore`
protocols without changing a caller.

`ingest_directory(Path("knowledge-base/noavia"), embedder, store)` reads
`.md`/`.txt` files in sorted path order. It chunks at 120 whitespace-delimited
words with a 24-word overlap and gives each chunk a stable id
`<source>#<index>`, plus `source`, `title`, and `chunk_index` metadata.
`retrieve(...)` returns at most three cosine-ranked chunks. Its default
threshold is **0.28**: if the highest score is below it (or the store is
empty), it returns no context with `low_confidence=true` and the explicit
`manual_review` fallback. Consumers must route that fallback rather than
inventing an answer.

## Design notes for whoever touches this next

- **Provider split is deliberate.** OpenAI supplies only inexpensive RAG
  embeddings; MiniMax supplies classification and grounded drafting to reduce
  chat operating cost. The service validates MiniMax JSON against
  `app/schemas.py::_ModelClassification`; do not route chat through the
  OpenAI embedding client or add provider fallback without a reviewed
  configuration change.
- **Point ids.** Qdrant requires point ids to be an unsigned int or a UUID;
  arbitrary caller-supplied strings aren't valid. `ingest_service._stable_id`
  deterministically maps any `id`/content string to a UUID via `uuid5`, so
  re-ingesting the same source upserts in place.
- **No collection auto-provisioning surprises.** `ensure_collection` only
  creates a collection during ingestion (when we know the embedding
  dimension from the batch just embedded); rag-lookup against a missing
  collection returns empty matches rather than creating one.
- **Extending the taxonomy or adding a new extraction field** doesn't need a
  code change for the taxonomy (pass `context.categories`); a new *output*
  field is a v2 (breaking) change per architecture doc §4 - ship it
  alongside the existing `v1` routes, don't mutate this one in place.
