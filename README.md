# NOAVIA canonical baseline

Recovered, canonical repository for the reusable Docker Compose substrate and
its first consumer, NOAVIA (n8n + Qdrant + classification). Future SaaS
products extend the same capability-module contracts rather than duplicating
product-specific infrastructure.
Implements the interface contract in
[`docs/capability-module-architecture.md`](docs/capability-module-architecture.md)
§3.3.

## What's here

| File | Purpose |
|---|---|
| `docker-compose.yml` | Network, volumes, reverse-proxy, n8n, Qdrant, classification-service slot |
| `.env.example` | Every env var the stack reads, with the `<FAMILY>_<PURPOSE>` naming convention — copy to `.env`, fill in, never commit `.env` |
| `Caddyfile` | HTTPS-ready reverse proxy config (automatic Let's Encrypt certs) |
| `.gitignore` | Keeps `.env` and local runtime state out of version control |
| `services/classification/` | `ai.classify-ticket.v1` / `ai.rag-lookup.v1` HTTP service (RAG & AI Integration Engineer) — see its own README for the interface contract |
| `knowledge-base/` | Reserved, product-neutral source material for future ingestion; it contains no customer data in this baseline |
| `scripts/` | Offline repository verification helpers; no deployment automation is included in Phase 1 |
| `docs/` | Architecture contract and recovery provenance |
| `docs/n8n-paperclip-api-access.md` | Approval-gated, project-isolated API access runbook for Paperclip/control-plane agents |
| `services/frontend/` | Test-mode support form and server-side private submission boundary |
| `evals/noavia_rag_eval.py` | Credential-free 40-case local RAG evaluation |
| `docs/noavia-offline-delivery-evidence.md` | Offline QA evidence, remaining live-verification boundaries, and release checklist |

## Quickstart

```sh
cp .env.example .env
# edit .env: real domain, real secrets, generate N8N_ENCRYPTION_KEY
docker compose up -d
```

n8n comes up behind the reverse proxy at `https://$N8N_PUBLIC_DOMAIN`.
Qdrant is reachable internally at `http://qdrant:6333` — no host port, no
public route.

## Security model

1. **Secrets never in code.** Every credential in `docker-compose.yml` is a
   `${VAR}` interpolation. Real values live only in `.env` (git-ignored) or a
   real secret-store in production — never hardcoded, never committed.
2. **Private networking by default.** All services share the `saas-internal`
   Docker network. It is a normal bridge network (not `internal: true`) so
   containers keep outbound internet access for OpenAI and Google API calls —
   isolation comes from *not publishing host ports*, not from blocking
   egress. Only `reverse-proxy` publishes `80`/`443`; every other service is
   reachable solely by DNS name (`n8n`, `qdrant`, …) on that network.
3. **HTTPS for anything public.** `reverse-proxy` (Caddy) is the single
   public entry point and auto-provisions/renews TLS certs. A service only
   becomes internet-reachable when someone deliberately adds a route for it
   in `Caddyfile` — the default posture is internal-only.
4. **Qdrant is authenticated and capability-scoped.** The Qdrant container holds `QDRANT_SERVICE_API_KEY` and has JWT RBAC enabled. `classification-service` alone receives `AI_QDRANT_API_KEY`, a short-lived JWT restricted to the collection(s) it needs. n8n receives neither a Qdrant URL nor key, and must use the classification API. Issue the JWT in the deploy secret-store with an `access` claim such as `[{"collection":"kb_documents","access":"rw"}]`; pre-create collections because collection-scoped credentials cannot create them. The signing/admin key must never be injected into an application container.
5. **Persistent volumes.** n8n workflow/credential state and Qdrant vector
   data survive container restarts/upgrades via named volumes
   (`n8n_data`, `qdrant_data`, `classification_data`). Back these up in
   production; they hold state, not secrets, but losing them loses data.

## Verification

Before deployment, validate the rendered Compose configuration and Caddyfile using deploy-time secret values (never paste secrets into commands or source control):

```sh
docker compose config --quiet
docker compose run --rm --no-deps reverse-proxy caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile
```

The repository contract check can be run offline with `./scripts/verify-baseline.sh`. It asserts Qdrant authentication/RBAC, that n8n has no Qdrant credential or URL, and the exact 10 MB Caddy rule for the NOAVIA webhook. An upload greater than 10 MB receives Caddy's `413` before reaching n8n.

## NOAVIA test portal

For a local demonstration without Docker or secrets, run this from the repository root:

```sh
NOAVIA_TEST_MODE=true uvicorn app:app --app-dir services/frontend --host 127.0.0.1 --port 8081
```

Open `http://127.0.0.1:8081/`, submit any valid dummy ticket, then stop it with `Ctrl-C`. The result is deterministic (`DEMO-0001`) and visibly includes mock classification JSON, three RAG sources and scores, fallback/routing/manual-review decisions, a processing log, and an **internal-draft-only** reply. The submitted details are discarded. In this mode no network call is made to Gmail, Google Sheets, n8n, model providers, or Qdrant; it needs no secrets or customer data.

Run all repository checks, including the existing script-style workflow check, with `./scripts/test.sh` from the repository root.

For container use, run `docker compose --profile frontend up --build`, then use
the internal frontend service through the reverse-proxy route configured by the deployer.
`NOAVIA_TEST_MODE=true` is the default: the form validates name, email, subject,
message, and an optional PDF. Browser code contains no webhook URL or
credential. Only an owner-approved controlled test may set the private
`NOAVIA_N8N_INTERNAL_WEBHOOK_URL` and disable test mode; it must match the
exact server-only `NOAVIA_N8N_INTERNAL_ALLOWED_ORIGIN` (default
`http://n8n:5678`). URLs with credentials, IP addresses, query strings, or
fragments are rejected, and private-service network failures return a
sanitized 502 response. The workflow stays inactive until that approval.

For RAG baseline measurement run `python3 evals/noavia_rag_eval.py`; see
`docs/noavia-rag-evaluation.md` for committed metrics and limitations.

For the separately maintained workflow QA record, run
`python3 tests/test_noavia_workflow.py` and consult
[`docs/noavia-offline-delivery-evidence.md`](docs/noavia-offline-delivery-evidence.md).
Those results do not prove that the stack has been deployed or that any live
integration works.

## Extending this for a new module or product

- **Add a module that talks to n8n/Qdrant:** add a service block, attach it
  to `saas-internal`, read secrets from env vars declared in `.env.example`
  (add new ones there following `<FAMILY>_<PURPOSE>` naming — see
  architecture doc §4). Don't touch existing service blocks.
- **Add a module that needs public HTTPS:** add a route in `Caddyfile`
  pointing at the service's container name/port. Don't publish its own host
  port in `docker-compose.yml` — everything public routes through Caddy.
- **Add a whole new product:** either extend this `docker-compose.yml`
  directly, or layer a product-specific override file
  (`docker compose -f docker-compose.yml -f product.yml up`) that adds its
  own services onto the same `saas-internal` network. This file is meant to
  stay product-agnostic — nothing here is NOAVIA-specific.

## Fail-fast on missing secrets

Per the interface contract, a module must fail with a clear structured error
at startup if a required env var is missing — not silently fall back to a
default. `docker-compose.yml` intentionally does not set defaults for
secret-bearing vars (`AI_CLASSIFY_API_KEY`, `OPENAI_API_KEY`,
`N8N_BASIC_AUTH_PASSWORD`, etc.); each service's own startup validation is
responsible for refusing to run without them.

## Open item inherited from the architecture doc — resolved

Architecture doc §7 asked whether `ai.classify-ticket`/`ai.rag-lookup` are
invoked as n8n sub-workflows or a standalone HTTP service. Resolved: **HTTP
service**, implemented in `services/classification/` (RAG & AI Integration
Engineer, issue SAI-5). Start it with
`docker compose --profile classification-service up -d --build`; n8n reaches
it at `http://classification-service:8080` on `saas-internal`, authenticating
with `Authorization: Bearer $AI_CLASSIFY_API_KEY`. See
`services/classification/README.md` for the full interface contract. No
infra rework was needed — the pre-existing slot in `docker-compose.yml` just
needed a `Dockerfile` and its environment block filled in with the `ai.*`
tuning vars now documented in `.env.example`.

## AI provider split

OpenAI is used only for inexpensive RAG embeddings (`text-embedding-3-small`).
MiniMax (`MiniMax-M3`) replaces OpenAI for structured ticket classification and
RAG-grounded reply drafting to reduce chat operating cost. Configure the split
with `AI_EMBEDDING_PROVIDER=openai`, `AI_EMBEDDING_MODEL=text-embedding-3-small`,
`AI_CHAT_PROVIDER=minimax`, and `AI_CHAT_MODEL=MiniMax-M3`; both provider keys
are secret-store values and are never stored in the workflow export.
