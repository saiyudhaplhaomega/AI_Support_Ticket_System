# services/

Supporting services. **Neither is required for the ticket pipeline**, which runs
entirely on native n8n nodes.

| Folder | Status | Purpose |
|---|---|---|
| `frontend/` | Optional | Flask app serving a ticket submission form and chat interfaces. Started by `compose.yaml` on port 8081. |
| `classification/` | **Retired** | A FastAPI classification microservice from an earlier iteration. |

## Why the classification service was retired

An earlier version ran ticket classification behind this HTTP service. It was removed
because everything the task requires is expressible in native n8n nodes, and the
service added a deployment surface, an authentication boundary and a second failure
domain without earning any of them.

The code is kept because it still holds working reference implementations of the
offline RAG path and the OpenAI client wrappers. **It is not wired into the current
pipeline.** Any documentation describing the ticket workflow as calling an HTTP
classification service describes the old architecture.
