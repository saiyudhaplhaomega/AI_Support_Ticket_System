# NOAVIA Part 1 features

- Required-field and email validation at webhook intake
- Optional PDF validation, Drive upload, text extraction, non-blocking
  extraction failure handling, and a stored `attachment_drive_link` included
  in full internal escalation emails
- OpenAI structured classification: category, urgency, sentiment, confidence,
  and summary
- Qdrant RAG retrieval using the three highest-scoring knowledge chunks
- Similarity threshold and the required low-confidence RAG statement
- OpenAI-generated, knowledge-grounded customer draft (stored only)
- Critical/high full internal email; medium brief email; low Sheets only
- Confidence below 0.6 forces `needs-manual-review`
- Google Sheets audit row and structured processing log
- Separate manual knowledge-base ingestion flow and persistent Docker volumes
- Admin-protected frontend knowledge-base update form for Markdown/text files;
  an authenticated n8n webhook enforces a 5 MB limit, replaces same-source
  chunks, and indexes uploads in the Qdrant collection used by ticket retrieval;
  the frontend serializes each source's update to prevent cleanup races
- Separate public support page, administrator sign-in page, and protected
  knowledge-base workspace with an HTTPS-only HttpOnly session cookie
- PDF magic-header verification in addition to type and size checks
- Controlled `live-kb-verification.md` source and a documented retrieval proof
