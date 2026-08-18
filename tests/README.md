# tests/

Contract tests for the workflow exports.

| File | Status |
|---|---|
| `test_noavia_workflow.py` | Current. Asserts the structural contracts of the n8n exports. |
| `test_noavia_workflow.legacy.py` | Historical. Targets the retired classification microservice under `services/classification/`. Kept as a record; not part of the current build. |

```bash
python tests/test_noavia_workflow.py
python scripts/verify_part1_workflows.py
```

## What is not covered

These are structural tests. They confirm the workflow is shaped correctly - they do not
confirm the AI behaves correctly. There is no golden set of tickets asserting expected
category, urgency and retrieved sources, which means a prompt edit can regress
classification quality with every test still green. That gap is documented rather than
hidden; it is how an urgency-classification bug survived longer than it should have.
