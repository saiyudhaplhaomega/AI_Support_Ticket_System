# Project rules for AI coding agents

## Project

NOAVIA AI Support Ticket System

Canonical working directory:

C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System

## Execution

- Kanban is the authoritative active-task state.
- Follow the assigned card and its acceptance criteria.
- Inspect existing implementation before proposing replacement work.
- Do not modify unrelated files.
- Run relevant tests after changes.
- Preserve reproducibility.
- Existing repository state is the source of truth.

## Review

- The implementer must not be the final reviewer of its own work.
- Substantial changes require an appropriate independent reviewer.
- Reviewer findings must include evidence.
- CHANGES REQUIRED routes back to implementation.
- PASS requires acceptance criteria and evidence.

## Safety

- Never place secrets, API keys, passwords, tokens, or private keys in source files, documentation, Kanban comments, or Hindsight.
- Do not perform destructive or irreversible operations without the approval required by company governance.
- Do not make production changes, purchases, legal commitments, external-account changes, or security-risk acceptance without required Owner approval.
- Do not silently broaden permissions.

## Git

- Do not force-push.
- Do not rewrite shared history.
- Do not push to a remote unless the task explicitly authorizes it.
- Keep changes scoped to the assigned task.


## Current Concurrency Rule

Until remote per-task Git worktree isolation is implemented, multiple agents may inspect this repository concurrently, but only one write-producing implementation flow may modify this working tree at a time.


<!-- NOAVIA-PART1-SIMPLE-ARCH:START -->

# NOAVIA Part 1 - Simplified Reproducible Architecture

This project implements Part 1 of the NOAVIA AI & Agent Engineer interview task.

The priority is:

simple
-> reproducible
-> easy to explain
-> directly aligned with the assignment
-> minimal unnecessary infrastructure

Do not preserve complexity merely because it already exists.

## Final reproducible deployment

The final project must be runnable with:

    docker compose up -d

The Compose project contains at minimum:

    n8n
    qdrant

Both services should use the same Docker Compose network.

Host access:

    n8n:
    http://localhost:5678

    Qdrant dashboard:
    http://localhost:6333/dashboard

Container-to-container Qdrant URL:

    http://qdrant:6333

Do not rely on Hostinger-specific:

- ai-net
- fixed container IP addresses
- host.docker.internal
- external custom networks

for the FINAL reproducible submission.

The live VPS may temporarily use existing infrastructure while development is
in progress, but the repository must remain self-contained and reproducible.

---

# Native n8n Qdrant Architecture

Use the native n8n Qdrant Vector Store integration wherever practical.

Do not introduce a custom RAG microservice when native n8n nodes satisfy the
assignment.

Qdrant remains a separate Docker service.

n8n is the orchestration layer.

## Knowledge Base Ingestion Workflow

Create a separate small ingestion workflow:

    Manual Trigger
 -> load NOAVIA knowledge-base files
 -> document loader
 -> text splitter
 -> embeddings
 -> Qdrant Vector Store: Add Documents
 -> collection: noavia_kb_v1

Use the existing 5-10 markdown/text NOAVIA knowledge-base files.

The ingestion workflow should be easy to rerun when the collection is rebuilt.

## Ticket Processing Workflow

Target conceptual flow:

    Webhook
 -> Validate
 -> optional PDF extraction
 -> AI Step 1: classification + analysis
 -> Qdrant Vector Store retrieval
 -> top 3 relevant chunks
 -> AI Step 2: grounded draft response
 -> urgency/confidence routing
 -> Google Sheets
 -> internal email when required
 -> webhook response

Prefer native n8n nodes over unnecessary custom middleware.

---

# Embeddings

The SAME embedding model must be used for:

    knowledge ingestion
    ticket retrieval

Do not preserve a vector-dimension mismatch.

Development embedding provider:

    OpenAI

Development embedding model:

    text-embedding-3-small

The Qdrant collection must be created with the dimension required by the
selected embedding model.

If the existing noavia_kb_v1 collection uses an incompatible dimension,
recreate the DEVELOPMENT collection cleanly rather than adding compatibility
hacks.

Retrieval:

    top_k = 3

Use a similarity threshold.

If no result passes the threshold, the draft must include the assignment's
required low-confidence RAG message:

    No specific policy found — this response is based on general knowledge.

---

# Development AI Provider Policy

During development:

    MiniMax
 -> classification / chat / grounded draft generation

    OpenAI
 -> embeddings only

This is a cost-saving development configuration.

Do not design workflow logic specifically around MiniMax.

Provider switching should remain simple.

Before FINAL submission / interview demo:

    OpenAI
 -> Step 1 classification
 -> Step 2 grounded draft
 -> embeddings

Then rerun the complete end-to-end validation.

The submitted workflow and README must describe the final OpenAI configuration.

---

# Authoritative Part 1 Functional Requirements

Ticket input:

- name required
- email required and valid
- subject required
- message body required
- PDF optional

AI Step 1 strict structured output:

- category
- urgency: critical / high / medium / low
- sentiment
- confidence: 0-1
- brief summary

RAG:

- 5-10 knowledge documents
- chunk documents
- generate embeddings
- store in Qdrant
- retrieve 3 most relevant chunks
- use similarity threshold
- preserve source document references

AI Step 2:

Generate a professional draft response using:

- original ticket
- classification
- retrieved knowledge

Tone should reflect customer sentiment.

Reference knowledge sources where applicable.

The generated response is a DRAFT.

Do NOT automatically send the draft to the customer.

Routing:

Critical / High:
    Google Sheets
    + internal email with full ticket, AI summary, draft

Medium:
    Google Sheets
    + brief internal email

Low:
    Google Sheets only

Confidence < 0.6:

    status = needs-manual-review

regardless of urgency.

Google Sheets must store:

- ticket ID
- timestamp
- name
- email
- subject
- category
- urgency
- sentiment
- confidence
- AI summary
- draft response
- knowledge sources
- status
- processing log

Important steps must have useful error handling and observable failures.

---

# Architecture Restraint

Avoid unnecessary:

- custom API layers
- custom auth between internal workflow components
- extra microservices
- multi-network Docker topology
- enterprise abstractions
- duplicated validation layers

unless they directly satisfy a requirement or solve a demonstrated problem.

When native n8n functionality can satisfy the task clearly and robustly,
prefer it.

---

# Worker Efficiency for NOAVIA

All company-efficient-execution rules apply.

Normal workers:

    inspect
 -> implement
 -> verify
 -> finish

Do not redesign this architecture from a small implementation ticket.

If genuinely blocked:

    one Claude consultation
 -> then lead escalation

Leads may use up to three Claude rounds for one unresolved blocker.

Prefer 3-4 independent focused tickets in parallel.

<!-- NOAVIA-PART1-SIMPLE-ARCH:END -->

