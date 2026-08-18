# Safe NOAVIA n8n tests

Run these commands from
`C:/Users/saiyu/Desktop/projects/Noavia/AI_Support_Ticket_System`.

Before testing, open the `notify.routing-email.v1` node in n8n and confirm
`NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON` maps every route to one test inbox. This
prevents tests from sending any customer-facing email.

## 1. Valid billing ticket

Send this only after importing and activating the ticket workflow:

```powershell
curl.exe -X POST "https://n8n.saiyudh.com/webhook/noavia/tickets/v1" `
 -H "Content-Type: application/json" `
 -H "<your Header Auth header>: <your test secret>" `
 -d '{"name":"NOAVIA Test","email":"noavia-test@example.invalid","subject":"Charged twice","message":"I was charged twice for the same subscription."}'
```

Expected result: HTTP 200, one test Sheet row, a `billing` classification,
up to three cited knowledge sources, and a draft response that is not sent to
the requester. This checks the normal RAG path.

## 2. Validation rejection

Use the same command but replace the request body with `{"name":"Test"}`.
Expected result: HTTP 400 with `VALIDATION_ERROR`; no model call, Sheet row,
or email. This proves validation fails before external work.

## 3. Low-similarity RAG fallback

Use a valid request whose message is unrelated to the knowledge base, for
example `Please explain quantum entanglement.`. Expected result: the stored
draft contains exactly `No specific policy found - this response is based on
general knowledge.` and has no policy sources.

## 4. PDF path

Use the generated, harmless invoice fixture
`output/pdf/noavia-dummy-invoice.pdf` with a billing test ticket. Expected
result: the execution reaches `Extract PDF Text`, adds attachment context to
classification, writes a row, and `invoice_check` says that an invoice PDF was
detected.

Repeat with `output/pdf/noavia-non-invoice-support-note.pdf` and an
account-access test ticket. Expected result: the same PDF path runs, but
`invoice_check` says `This PDF does not appear to be an invoice`. The full
internal email also shows this attachment check and its Drive link.

The workflow extracts the PDF's embedded text layer, caps it at 12,000
characters, labels it as untrusted document content, and appends it to the
classifier input. A scanned, password-protected, or corrupted PDF may not
produce text; the ticket still proceeds and the Sheet records that the invoice
status could not be determined. This is document classification, not malware
scanning: do not treat it as antivirus protection.

Why these tests: together they exercise normal, rejection, low-RAG, and PDF
branches without requiring customer data.
