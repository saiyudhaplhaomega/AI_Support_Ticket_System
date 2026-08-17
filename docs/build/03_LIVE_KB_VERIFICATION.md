# Live knowledge-base and portal verification

Run every command from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.

This guide proves that a browser administrator upload reaches n8n, creates
Qdrant vectors, and is retrieved by a ticket. It uses only the harmless
`knowledge-base/noavia/live-kb-verification.md` document.

## 1. Configure the frontend runtime

Copy `.env.example` to `.env` if it does not already exist. Set only these
values in `.env`; do not commit that file:

```dotenv
NOAVIA_TEST_MODE=false
NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/kb/update/v1
NOAVIA_N8N_PUBLIC_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/tickets/v1
NOAVIA_N8N_WEBHOOK_HEADER_NAME=<the Header Auth header name>
NOAVIA_N8N_WEBHOOK_HEADER_VALUE=<the Header Auth secret>
NOAVIA_KB_ADMIN_USERNAME=<administrator username>
NOAVIA_KB_ADMIN_PASSWORD=<long administrator password>
```

Run `docker compose up -d --build frontend`.

Success means `docker compose ps` shows `frontend` running. Use HTTPS when
hosting this portal because the administrator session cookie is deliberately
marked Secure and is not accepted over plain HTTP.

## 2. Create the initial collection

In n8n, import and activate `workflow/noavia/workflow.noavia-kb-ingestion.v1.json`.
Bind OpenAI and Qdrant credentials, then execute its Manual Trigger once.

Run:

```powershell
curl.exe http://localhost:6333/collections/noavia_kb_v1
```

Success means the response includes collection configuration rather than
`Collection not found`. This initial run is mandatory: the update workflow
updates sources but cannot prove that the base knowledge set was ever loaded.

## 3. Verify administrator upload

Open the deployed frontend URL, choose **Administrator**, and sign in with the
runtime username and password. On the knowledge-base page upload
`knowledge-base/noavia/live-kb-verification.md`.

Success means the page reports that n8n accepted the document. In n8n, the
matching execution must finish at **Respond KB Update Success** and show the
source filename plus the new version.

## 4. Prove retrieval from a ticket

Send this test through the public support page or the ticket webhook:

```text
Subject: Controlled knowledge-base retrieval
Message: What does NOAVIA-KB-LIVE-20260817 confirm?
```

Success means the ticket execution's RAG node includes
`live-kb-verification.md` in its top three source metadata. The Sheet row and
internal notification must list that source. This proves the update changed the
collection the ticket workflow actually queries.

## 5. Required negative checks

| Scenario | Expected result |
| --- | --- |
| No administrator session | KB API returns HTTP 401; no n8n execution |
| `.pdf` uploaded to KB page | Browser blocks it; API also returns HTTP 422 |
| KB file over 5 MB | Browser/API reject it; no Qdrant change |
| Ticket with renamed non-PDF file | API rejects the missing `%PDF-` header |
| Unrelated ticket | No policy source passes threshold and the required fallback sentence is used |
| Re-upload same KB filename | New version is indexed before old chunks are cleaned up |

Why these checks: they prove the positive retrieval path, authorization,
validation, fallback behavior, and safe source replacement in one controlled
batch.
