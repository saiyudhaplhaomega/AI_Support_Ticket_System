# Vercel deployment and Google administrator login

> Deployment note: after connecting this repository to Vercel, push a new commit to `main` (or redeploy from the Vercel dashboard) so Vercel creates its first Git-backed production deployment.

Run every command from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System/services/frontend`.

The support portal is a FastAPI Vercel Function. n8n and Qdrant stay on the
existing server; Vercel hosts the browser UI and securely forwards requests to
the already-published n8n webhooks.

## 1. Create the Google OAuth client

In Google Cloud Console, create an OAuth client of type **Web application**.
Add this authorized redirect URI after Vercel provides the production domain:

```text
https://<your-vercel-domain>/api/auth/google/callback
```

Use HTTPS and copy the URI exactly. Google rejects mismatched callback URIs.
Do not download or commit the client-secret file into this repository.

## 2. Configure Vercel environment variables

In the Vercel project, add these variables for **Production** and **Preview**:

```text
NOAVIA_TEST_MODE=false
NOAVIA_N8N_PUBLIC_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/tickets/v1
NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/kb/update/v1
NOAVIA_N8N_WEBHOOK_HEADER_NAME=<Header Auth header name>
NOAVIA_N8N_WEBHOOK_HEADER_VALUE=<Header Auth secret>
GOOGLE_OAUTH_CLIENT_ID=<Google client ID>
GOOGLE_OAUTH_CLIENT_SECRET=<Google client secret>
NOAVIA_GOOGLE_ADMIN_EMAILS=<your approved Google email>
NOAVIA_SESSION_SECRET=<a new random 32-byte-or-longer secret>
NOAVIA_GOOGLE_REDIRECT_URI=https://<your-vercel-domain>/api/auth/google/callback
```

For the public assistant, private administrator assistant, and document
library, also add these **Production** variables. The URLs are not secrets;
the matching Header Auth values are secrets and must be copied from the
corresponding n8n Header Auth credential, never from a browser or Git file.

```text
NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/public-chat/v1
NOAVIA_N8N_PUBLIC_CHAT_HEADER_NAME=<public chat Header Auth header name>
NOAVIA_N8N_PUBLIC_CHAT_HEADER_VALUE=<public chat Header Auth secret>
NOAVIA_N8N_ADMIN_CHAT_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/admin-chat/v1
NOAVIA_N8N_ADMIN_CHAT_HEADER_NAME=<admin chat Header Auth header name>
NOAVIA_N8N_ADMIN_CHAT_HEADER_VALUE=<admin chat Header Auth secret>
NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/documents/v1
NOAVIA_N8N_SOURCE_LIBRARY_WEBHOOK_URL=https://n8n.saiyudh.com/webhook/noavia/source-library/v1
```

The document-manager and source-library webhooks use
`NOAVIA_N8N_WEBHOOK_HEADER_NAME` and `NOAVIA_N8N_WEBHOOK_HEADER_VALUE` shown
in the first block. Save the variables, then redeploy the Vercel production
deployment. Success means `/chat` accepts a question and `/admin/assistant`
answers only after Google sign-in; the knowledge library stays empty until the
source-store bootstrap has run and documents have been indexed.

`NOAVIA_KB_ADMIN_USERNAME` and `NOAVIA_KB_ADMIN_PASSWORD` are no longer needed
for browser access. Keep `NOAVIA_KB_ADMIN_TOKEN` only if an approved server-side
programmatic client still uses that compatibility path.

## 3. Deploy

From `services/frontend`, run:

```powershell
vercel --prod
```

Success means Vercel prints a production HTTPS URL. Open that URL, choose
**Administrator**, sign in with the allowlisted Google account, and confirm
that `/admin/knowledge-base` opens. A different Google account must receive a
403 response and must not be able to invoke the KB-update API.

## 4. Connect the GitHub repository

In Vercel, open the project settings and connect
`saiyudhaplhaomega/AI_Support_Ticket_System`. Set the Vercel root directory to
`services/frontend`. Future pushes to the selected production branch then build
this same FastAPI app. Do not add n8n credentials or Google secrets to GitHub.

## 5. Final live proof

Follow [03_LIVE_KB_VERIFICATION.md](03_LIVE_KB_VERIFICATION.md). The browser
must upload `live-kb-verification.md`, n8n must index it, and a ticket must
retrieve it as a source before the RAG feature is marked complete.

Why this deployment shape: Vercel is ideal for the public portal and OAuth
callback, while the existing n8n/Qdrant server keeps workflow credentials and
vector storage outside the browser-facing application.
