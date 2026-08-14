# Getting started

## Safe local portal demo

**Configured but unexecuted:** this starts the checked-in frontend on loopback with test mode explicitly enabled. Test mode returns a synthetic `TEST-...` identifier and does not contact n8n. It requires existing frontend Python dependencies; it neither installs packages nor reads `.env`.

```sh
cd services/frontend
NOAVIA_TEST_MODE=true python3 -m uvicorn app:app --host 127.0.0.1 --port 8081
```

In a second terminal, submit a dummy ticket. Stop the foreground server with `Ctrl-C` in the first terminal.

```sh
curl -sS -X POST http://127.0.0.1:8081/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo User","email":"demo@example.test","subject":"Demo","message":"Local test only"}'
```

Expected scope: local JSON with `"mode":"test"`; no workflow, email, sheet, model, vector database, or external service is invoked. Do not set `NOAVIA_TEST_MODE=false`, configure a webhook, activate the workflow, or use real ticket data.

## Offline checks

**Verified:** recorded credential-free evidence covers:

```sh
python3 tests/test_noavia_workflow.py
(cd services/classification && python3 -m pytest -q)
(cd services/frontend && python3 -m pytest -q)
```

These commands do not prove containers, proxy behavior, n8n import/activation, or any external integration. See [Testing guide](testing-guide.md).
