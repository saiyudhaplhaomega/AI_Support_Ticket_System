# Start here

> For a full reading path across every document, see [99_DOC_ORDER.md](99_DOC_ORDER.md).
> For installation, the [root README](../README.md) is more current than this page.

This is the AI support ticket system. The delivery has ticket processing,
initial knowledge-base ingestion,
and authenticated knowledge-base-update workflows. It also includes separate
public support, administrator sign-in, and knowledge-base pages. Do not use
real customer tickets while you are validating the workflow: the configured
Google Sheet and notification route are live outputs.

## Prerequisites

- Docker Desktop running
- an OpenAI credential in n8n (used for classification, drafting, and
  `text-embedding-3-small`)
- a Qdrant credential in n8n pointing to `http://qdrant:6333`
- Google Sheets and Gmail credentials bound only in your n8n instance

## First safe check

1. Open a terminal in the repository root.
2. Run `docker compose up -d`.
3. Run `curl.exe http://localhost:6333/readyz`.
4. Open `http://localhost:8081` for the safe portal demonstration.

Success is `all shards are ready` and the portal loads. The frontend starts in
safe test mode until runtime environment values explicitly enable live webhooks.

Continue with [01_BUILD_ORDER.md](01_BUILD_ORDER.md).
