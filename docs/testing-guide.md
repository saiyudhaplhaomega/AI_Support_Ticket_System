# Testing guide

## Credential-free commands

**Verified:** recorded passing evidence exists for:

```sh
python3 tests/test_noavia_workflow.py
(cd services/classification && python3 -m pytest -q)
(cd services/frontend && python3 -m pytest -q)
./scripts/verify-baseline.sh
```

The workflow harness parses the export and runs selected Code-node behavior; it never imports or activates n8n. Classification tests use local/mocked boundaries. Frontend tests exercise validation, test mode, and failure handling without a real workflow. The baseline script invokes the workflow harness.

## Evidence boundary

**Configured but unexecuted:** passing these checks does not establish Docker/Compose startup, Caddy or TLS, n8n import/activation, real PDF extraction, model or Qdrant access, OAuth permissions, Sheets writes, Gmail delivery, retention, or production monitoring.

**Planned / future work:** run those integrations only through an owner-approved live test with least-privilege test credentials, test-only destinations, and redacted evidence. Never record secrets or customer data.

**Verified:** `python3 evals/noavia_rag_eval.py` uses the checked-in fixture and writes `evals/noavia_rag_eval_results.json`. Because it rewrites a tracked result artifact, run it only when intentionally refreshing evidence and review its diff.
