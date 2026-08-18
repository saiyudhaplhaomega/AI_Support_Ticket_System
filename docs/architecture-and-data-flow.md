# Architecture and data flow

> Historical platform note: this document describes the retired
> Caddy/classification-service architecture. For the current Part 1 design,
> read [the current Part 1 architecture](current-architecture.md).

**Verified structural path:**

`authenticated webhook → validate/normalize → optional PDF extraction → classify → RAG lookup → route → Sheets/email nodes → response`

The export is inactive. Validation branches before AI and delivery. The internal classification service exposes versioned classify/retrieval endpoints.

## Compact evidence map

| Segment | Repository evidence | Runtime status |
| --- | --- | --- |
| Browser → frontend test mode | Frontend tests exercise a synthetic local acceptance response. | **Verified mock / local behavior:** test mode does not request n8n. |
| Webhook → validation → routing | Inactive export plus structural/Code-node harness. | **Verified structural behavior; Configured but unexecuted** in n8n. |
| Workflow → classification/RAG | HTTP contracts and service tests, including local RAG/mocked providers. | **Verified offline contracts; Configured but unexecuted** against a running service, hosted models, or Qdrant. |
| Workflow → Sheets/Gmail | Exported nodes and environment/credential references. | **Configured but unexecuted:** no provider call is evidenced. |
| Caddy/Compose ingress | Checked-in runtime declarations. | **Configured but unexecuted:** no container, network, TLS, or proxy behavior is established. |

## Data boundary

**Verified:** n8n holds the classification-service bearer token; Compose does not provide n8n with Qdrant credentials. The service owns provider and Qdrant access.

**Planned / future work:** validate every configured segment through an approved controlled live test. Offline evidence is not end-to-end delivery evidence.
