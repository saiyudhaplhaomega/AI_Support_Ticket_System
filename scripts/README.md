# scripts/

Generation, verification and test-fixture tooling. Nothing here runs in production;
these are development utilities.

| Script | What it does |
|---|---|
| `build_part1_workflow.py` | **Generates** `workflow.noavia-ticket-pipeline.v1.json`. The tracked export is generated, not hand-edited - change this file, not the JSON. Deterministic and safe to re-run. |
| `verify_part1_workflows.py` | Credential-free structural checks across every workflow export: required nodes exist, validation strings are present, routing thresholds intact, ingestion and retrieval embedding dimensions match. Prints `PASS:` on success. |
| `create_dummy_invoice_pdf.py` | Test fixture: a clean invoice with no problem described. Exercises the attachment path without an escalation trigger. |
| `create_disputed_invoice_pdf.py` | Test fixture: an invoice whose duplicate-charge complaint exists **only inside the PDF**. This is the fixture that proves the classifier reads attachment text when judging urgency. |
| `create_non_invoice_pdf.py` | Test fixture: a support note that is not an invoice, with a problem described inside it. |
| `test.sh`, `verify-baseline.sh` | Shell wrappers from the earlier microservice era. Superseded by the Python verifier. |

## Typical loop

```bash
python scripts/build_part1_workflow.py
python scripts/verify_part1_workflows.py
```

PDF fixtures write to `output/pdf/` (gitignored) and need `reportlab`:

```bash
pip install reportlab
python scripts/create_disputed_invoice_pdf.py
```

## Editing the workflow

`build_part1_workflow.py` reads the tracked export, strips the AI and routing nodes,
rebuilds them from the definitions in the script, and writes the file back. Because it
defines those nodes completely rather than patching incrementally, running it twice
produces identical output. Hand-editing the JSON works until the next regeneration
silently discards your change.
