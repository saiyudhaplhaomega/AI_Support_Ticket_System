# SAI-16 recovery manifest

Recovered on 2026-08-13 from the misplaced onboarding workspace:

`/paperclip/instances/default/projects/63075ab8-5b80-4aee-a6cc-f0e979e84826/1947edbe-6eb0-4646-994c-dabc420ce512/_default`

This is a provenance record, not a deployment record. Phase 1 copied only
repository-safe artifacts into this canonical repository and made no external
service, credential, network, n8n, Qdrant, Google Sheets, or SMTP changes.

| Source | Canonical destination | SHA-256 | Recovery decision |
|---|---|---|---|
| `infra/docker-compose.yml` | `docker-compose.yml` | `885fc75741af223b97d6c38771e3b92b998ed67a7c0150186e7ea7085c613ed3` | included |
| `infra/.env.example` | `.env.example` | `5ea3aa248a1188000f9f329371ac0e14e69b0b1650459d34dcc3f128d1b33d48` | included, placeholders only |
| `infra/.gitignore` | `.gitignore` | `56f845c6015d133199383e6390713a7556c9ec945271e14e949e73938935d590` | included then strengthened for repository-wide caches/data |
| `infra/Caddyfile` | `Caddyfile` | `00aa9b1a7ec685e4a5eaa80644e8f9916e83f5823f6eee17cb318c07d3556d60` | included as configuration artifact; not deployed |
| `infra/README.md` | `README.md` | `d2fc7dbe41d8fb672dc3b5988bcfd30be8e741ffc5b63ff67005171b1debc21e` | included with canonical-path edits |
| `infra/workflows/noavia/` | `workflow/noavia/` | directory manifest below | included |
| `infra/services/classification/` | `services/classification/` | directory manifest below | included, excluding generated cache directories/files |
| `tests/test_noavia_workflow.py` | `tests/test_noavia_workflow.py` | `5cf7aa248a1188000f9f329371ac0e14e69b0b1650459d34dcc3f128d1b33d48` | included with canonical-path edit |
| `capability-module-architecture.md` | `docs/capability-module-architecture.md` | `4dd8e800c11f07edd8974894f9d0ebcf231ec10ee5a75bc4a3c39de78d640e54` | included |

## Directory artifact hashes

- `infra/workflows/noavia/workflow.noavia-ticket-pipeline.v1.json` — `537dc1dc16eefa85215b5ea1c0b5698e84b9e968980031dc842fe03082f1a682`
- `infra/workflows/noavia/README.md` — `c055ffbb56e51be495e69a0de9592b7daf57e9c83f7b4d948eaf56be713ef0c1`
- `infra/services/classification/` source, requirements, Dockerfile, documentation, and tests were copied without content changes; generated `__pycache__/`, `.pytest_cache/`, `*.pyc`, and `*.pyo` artifacts were excluded.

## Deliberately excluded

- `.claude/settings.local.json` (editor-local configuration, not a NOAVIA artifact)
- Python bytecode and pytest caches
- Any `.env` file, private key, credential, volume, database, or generated runtime state (none were recovered)
- Issue attachments and onboarding sample files, which are not canonical application artifacts

`knowledge-base/` and `scripts/` were established as safe repository contracts:
the former is empty except for handling guidance, and the latter contains only
an offline verification wrapper.

## Verification evidence

- `scripts/verify-baseline.sh` completed successfully on 2026-08-13, confirming
  the workflow's 23 nodes plus validation, audit telemetry, fallback, and
  delivery-contract checks.
- A tracked-file scan on 2026-08-13 found no private-key blocks or common live
  credential markers (AWS access keys, Slack tokens, GitHub tokens, or OpenAI
  secret-key patterns).
- `git check-ignore -v` confirms `.env` files are excluded. The repository
  policy also excludes runtime data, volumes, caches, Python bytecode, and
  generated test artifacts; none are tracked in this baseline.
- The recovered artifact commit is `ebd1c93`; the access-runbook commit is
  `85c52f4`. At the time of recovery, publication was pending a GitHub
  credential. This historical note is superseded by the current release
  handoff and does not describe the present remote state.
