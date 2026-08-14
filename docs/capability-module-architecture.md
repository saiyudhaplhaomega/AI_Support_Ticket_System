# Capability-Module Architecture (v1)

Status: adopted for the current NOAVIA baseline · Owner: Automation Workflow Engineer · Consumers: RAG & AI Integration Engineer, Infra & DevOps Engineer, QA & Security Engineer

## 1. Purpose

This defines how the SaaS factory splits work into independently buildable, independently versioned **capability modules**, and the contract each module must expose so any product (starting with NOAVIA, a support-ticket pipeline) can compose them without touching internals. It lands before any NOAVIA-specific n8n logic is built so the workflow is reusable by construction, not by retrofit.

## 2. Module boundaries

Four module families, one per company role. A product workflow (n8n) orchestrates calls across them; no family reaches into another's internals.

| Family | Owner | Responsibility | Never does |
|---|---|---|---|
| **`workflow.*`** | Automation Workflow Engineer | Orchestration: triggers, ingestion, routing, node graphs, calling other modules, delivering output (Sheets/email/etc.) | Doesn't implement classification/embedding logic or provision infra |
| **`ai.*`** | RAG & AI Integration Engineer | Embeddings, Qdrant retrieval, OpenAI-compatible structured classification/extraction | Doesn't own workflow triggers or infra provisioning |
| **`infra.*`** | Infra & DevOps Engineer | Docker Compose service defs, networking, secrets substrate, reverse proxy/HTTPS | Doesn't write workflow or AI logic |
| **`qa.*`** (cross-cutting) | QA & Security Engineer | Validation schemas, error-handling conventions, logging conventions, security/least-privilege review | Doesn't design or own module logic — reviews and can block, doesn't redesign |

Boundary rule: a module in one family talks to another family **only** through the interface contract in §3, never via shared DB tables, shared files, or reaching into another module's n8n sub-workflow internals. Everything crosses the boundary as a JSON request/response.

## 3. Interface contracts

Every module (regardless of family) exposes a contract with these five parts. This is the reusability guarantee — a consumer only ever needs to read this, not the implementation.

1. **Interface ID** — `family.module-name` (see naming convention §4)
2. **Input schema** — JSON Schema, versioned, with required/optional fields and types
3. **Output schema** — JSON Schema; success and error shapes both defined (see §5)
4. **Invocation mechanism** — how a consumer calls it (n8n sub-workflow via `Execute Workflow` node, HTTP endpoint, etc.) and the auth/secret pattern used (env var name pattern, never the value)
5. **SLA/behavior notes** — idempotency, timeout, retry expectations, side effects

### 3.1 `ai.classify-ticket` (v1) — owned by RAG & AI Integration Engineer

- **Input**: `{ "text": string, "context"?: object, "locale"?: string }`
- **Output (success)**: `{ "category": string, "confidence": number (0-1), "tags": string[], "urgency"?: string, "sentiment"?: string, "summary"?: string, "raw_model_output"?: object }` — structured, never free text as the primary field. `category`, `confidence`, and `tags` are the original required fields; `urgency`, `sentiment`, and `summary` are additive optional fields (§4) added when the chat provider moved to MiniMax — the service fills them on every call in practice, but consumers must not treat them as required.
- **Output (error)**: see shared error envelope §5
- **Invocation**: internal HTTP service at `POST /ai/classify-ticket/v1`; n8n calls it with an HTTP Request node. Consumers never call Qdrant directly for embeddings or MiniMax directly for chat.
- **Secrets**: the workflow receives only `AI_CLASSIFY_API_KEY` for service authentication. The service receives its Qdrant/OpenAI/MiniMax configuration from Infra; neither secret values nor direct upstream credentials are exposed to the workflow. Embeddings use `OPENAI_API_KEY` (model `text-embedding-3-small`); chat (classification and grounded draft replies) uses `MINIMAX_API_KEY` (model `MiniMax-M3`) — OpenAI is never called for chat.
- **SLA**: synchronous, target < 5s p95, must return the error envelope (not throw) on timeout/model failure so the caller can route to a fallback/manual queue.

### 3.2 `ai.rag-lookup` (v1) — owned by RAG & AI Integration Engineer

- **Input**: `{ "query": string, "top_k"?: number, "filter"?: object }`
- **Output (success)**: `{ "matches": [{ "id": string, "score": number, "content": string, "metadata": object }] }`
- **Invocation / secrets / SLA**: same pattern as 3.1, at `POST /ai/rag-lookup/v1`.

### 3.3 `infra.secrets-and-network` (v1) — owned by Infra & DevOps Engineer

- **Contract, not an API**: a documented set of env var names each module declares it needs (e.g. `OPENAI_API_KEY`, `QDRANT_URL`, `SMTP_*`, `GOOGLE_SHEETS_*`), a Compose network name modules attach to (`saas-internal`), and which services get a public HTTPS ingress vs. stay internal-only.
- **Consumers** declare required env vars in their module doc; Infra provisions them outside code (secret-store/`.env`, never committed). A module must fail with a clear structured error at startup if a declared var is missing — not fall back to a hardcoded default. Conditional credentials must name their security mode explicitly and default to the more restrictive setting: for example, `AI_QDRANT_API_KEY` is required while `AI_QDRANT_AUTH_ENABLED=true` (the default), and may be omitted only when that flag is explicitly `false` for an unauthenticated Qdrant deployment.

### 3.4 `qa.validation-and-logging` (v1) — owned by QA & Security Engineer, applies to all modules

- **Input validation**: every module validates its input against its published JSON Schema before doing work; invalid input returns the error envelope with `error.code = "VALIDATION_ERROR"` — it never partially executes.
- **Logging**: every module emits structured (JSON) logs with at minimum `{ ts, module, interface_id, version, correlation_id, level, message }`. `correlation_id` is generated at workflow ingestion and threaded through every downstream module call so one ticket's full path is traceable.
- **Security review checklist** (applied per module before it ships): secrets never in code/logs, least-privilege scopes on any credential, input validation present, structured error handling present, no unbounded retries/loops.

### 3.5 `workflow.noavia-ticket-pipeline` (v1) — owned by Automation Workflow Engineer

- The NOAVIA n8n workflow itself: ingest → `ai.classify-ticket` → `ai.rag-lookup` → route → Sheets/email. This is a **consumer**, not itself reused by other modules, but it must be built from generic sub-workflow nodes (`ingest.*`, `route.*`, `notify.*`) so future products swap the specific trigger/output nodes without touching the classify/RAG calls.

## 4. Naming & versioning conventions

- **Interface ID**: `<family>.<module-name>` in kebab-case, e.g. `ai.classify-ticket`, `workflow.noavia-ticket-pipeline`, `infra.secrets-and-network`.
- **Versioning**: semantic-ish but simplified for workflow modules — `v<major>` suffix on the n8n sub-workflow name (`ai.classify-ticket.v1`). Bump major on any breaking input/output schema change; additive optional fields do not require a bump.
- **Breaking change = new major, old version stays live** until all consumers migrate (no silent in-place breaking edits to a shipped interface). Whoever owns the module posts a heads-up to consumers before deprecating the old version.
- **n8n asset naming**: workflow files/exports use `<interface-id>.<version>.json` (e.g. `ai-classify-ticket.v1.json`) so they're identifiable outside the n8n UI too.
- **Env var naming**: `<FAMILY>_<PURPOSE>` upper snake case, e.g. `AI_CLASSIFY_API_KEY`, `QDRANT_URL`, `INFRA_NETWORK_NAME`. No product name in shared env vars — product-specific values (e.g. NOAVIA's Sheet ID) are passed as workflow input, not baked into a global env var name.

## 5. Shared error envelope (used by every module, every family)

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR | UPSTREAM_TIMEOUT | UPSTREAM_ERROR | AUTH_ERROR | INTERNAL_ERROR",
    "message": "human-readable, no secrets/PII",
    "interface_id": "ai.classify-ticket",
    "version": "v1",
    "correlation_id": "..."
  }
}
```

Success responses are `{ "ok": true, "data": { ...per interface output schema... } }`. This envelope is what makes modules swappable — a workflow node checks `ok` and branches, regardless of which module or version answered.

## 6. What this unblocks

- RAG & AI Integration Engineer builds `ai.classify-ticket` and `ai.rag-lookup` against §3.1/3.2 — can proceed independently of the workflow build.
- Infra & DevOps Engineer provisions Compose/network/secrets per §3.3 — the env var names above are the contract they scaffold against.
- QA & Security Engineer reviews every module against the §3.4 checklist before it ships.
- Automation Workflow Engineer builds `workflow.noavia-ticket-pipeline` (v1) as the first consumer, calling `ai.classify-ticket`/`ai.rag-lookup` only through their published interfaces.

## 7. Resolved implementation decision

`ai.classify-ticket.v1` and `ai.rag-lookup.v1` are implemented as an internal,
standalone HTTP service, not n8n sub-workflows. This decision is reflected in
`services/classification/` and lets future non-n8n consumers use the same
versioned contracts. It is a repository implementation decision; live service
deployment and integration remain unverified (see
`docs/noavia-offline-delivery-evidence.md`).

## 8. Provider split (SAI-32)

The reusable AI module uses OpenAI only for `text-embedding-3-small` embedding
calls. MiniMax (`MiniMax-M3`, Bearer `MINIMAX_API_KEY`) is the sole chat
provider for classification and grounded drafting, reducing chat operating
cost without changing Qdrant retrieval. The NOAVIA workflow requests exactly
top-three RAG matches and calls the internal `ai.grounded-draft.v1` endpoint;
the service retains source-file citations. When no qualifying source exists it
returns exactly: `No specific policy found — this response is based on general knowledge.`
