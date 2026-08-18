"""Credential-free structural acceptance checks for the NOAVIA workflow exports."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "workflow/noavia/workflow.noavia-ticket-pipeline.v1.json"
INGEST = ROOT / "workflow/noavia/workflow.noavia-kb-ingestion.v1.json"
UPDATE = ROOT / "workflow/noavia/workflow.noavia-kb-webhook-update.v1.json"
PUBLIC_CHAT = ROOT / "workflow/noavia/workflow.noavia-public-chat.v1.json"
ADMIN_CHAT = ROOT / "workflow/noavia/workflow.noavia-admin-chat.v1.json"
LIBRARY = ROOT / "workflow/noavia/workflow.noavia-kb-library.v1.json"
DOCUMENT_MANAGER = ROOT / "workflow/noavia/workflow.noavia-document-manager.v1.json"
SOURCE_LIBRARY = ROOT / "workflow/noavia/workflow.noavia-source-library.v1.json"
SOURCE_BOOTSTRAP = ROOT / "workflow/noavia/workflow.noavia-source-store-bootstrap.v1.json"


def names(workflow: dict) -> set[str]:
    return {node["name"] for node in workflow["nodes"]}


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def main() -> None:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    ingest = json.loads(INGEST.read_text(encoding="utf-8"))
    update = json.loads(UPDATE.read_text(encoding="utf-8"))
    public_chat = json.loads(PUBLIC_CHAT.read_text(encoding="utf-8"))
    admin_chat = json.loads(ADMIN_CHAT.read_text(encoding="utf-8"))
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    document_manager = json.loads(DOCUMENT_MANAGER.read_text(encoding="utf-8"))
    source_library = json.loads(SOURCE_LIBRARY.read_text(encoding="utf-8"))
    source_bootstrap = json.loads(SOURCE_BOOTSTRAP.read_text(encoding="utf-8"))
    required_ticket_nodes = {
        "Ingest Support Ticket", "Validate and Normalize", "Extract PDF Text",
        "build.classify-prompt.v1", "ai.classify-ticket.v1", "parse.classify-response.v1",
        "RAG Vector Search", "Embeddings OpenAI (RAG)", "Collect RAG Matches",
        "build.draft-prompt.v1", "ai.draft-response.v1", "parse.draft-response.v1",
        "route.by-classification.v1", "notify.google-sheets.v1", "notify.routing-email.v1",
    }
    assert required_ticket_nodes <= names(ticket), required_ticket_nodes - names(ticket)
    assert {"Manual Trigger - Ingest NOAVIA KB", "Load NOAVIA Knowledge Files", "Document Loader - KB Markdown", "Recursive Character Text Splitter - 800/120", "Qdrant Vector Store - Add Documents", "Embeddings OpenAI - text-embedding-3-small"} <= names(ingest)
    classifier = node(ticket, "parse.classify-response.v1")["parameters"]["jsCode"]
    assert "ok: true" in classifier and "Model output did not match the required schema" in classifier
    assert "envelope.statusCode" in classifier and "...base, ok: false" in classifier
    assert "attachment_is_invoice" in classifier and "attachment_invoice_reason" in classifier
    classify = node(ticket, "ai.classify-ticket.v1")
    assert classify["type"] == "n8n-nodes-base.openAi"
    assert classify["parameters"]["resource"] == "chat" and classify["parameters"]["simplifyOutput"] is True
    assert "response.message?.content" in classifier
    draft = node(ticket, "build.draft-prompt.v1")["parameters"]["jsCode"]
    assert "No specific policy found — this response is based on general knowledge." in draft
    route = node(ticket, "route.by-classification.v1")["parameters"]["jsCode"]
    assert "needs-manual-review" in route and "emailPolicy" in route
    assert "queue_label: display(category)" in route
    assert "This PDF does not appear to be an invoice" in route
    assert "Attachment check: ${row.invoice_check}" in route
    subject = node(ticket, "notify.routing-email.v1")["parameters"]["subject"]
    assert "route.queue_label" in subject and "route.queue +" not in subject
    columns = node(ticket, "notify.google-sheets.v1")["parameters"]["columns"]["value"]
    required_columns = {"ticket_id", "timestamp", "name", "email", "subject", "category", "urgency", "sentiment", "confidence", "ai_summary", "draft_response", "knowledge_sources", "status", "processing_log", "attachment_drive_link"}
    assert required_columns <= set(columns), required_columns - set(columns)
    sheet_schema = node(ticket, "notify.google-sheets.v1")["parameters"]["columns"]["schema"]
    assert required_columns <= {field["id"] for field in sheet_schema}
    assert node(ticket, "Embeddings OpenAI (RAG)")["parameters"]["model"] == "text-embedding-3-small"
    assert node(ingest, "Embeddings OpenAI - text-embedding-3-small")["parameters"]["options"]["dimensions"] == 1536
    assert {"Receive KB Update", "Validate KB Upload", "Delete Previous Source Versions", "Qdrant Vector Store - Update Documents", "Embeddings OpenAI - text-embedding-3-small", "Respond KB Update Success", "Respond KB Update Error"} <= names(update)
    assert node(update, "Receive KB Update")["parameters"]["path"] == "noavia/kb/update/v1"
    assert node(update, "Qdrant Vector Store - Update Documents")["parameters"]["qdrantCollection"]["value"] == "noavia_kb_v1"
    assert node(update, "Embeddings OpenAI - text-embedding-3-small")["parameters"]["options"]["dimensions"] == 1536
    assert "5 * 1024 * 1024" in node(update, "Validate KB Upload")["parameters"]["jsCode"]
    assert "Buffer.from" not in node(update, "Validate KB Upload")["parameters"]["jsCode"]
    assert "Number.parseInt" in node(update, "Validate KB Upload")["parameters"]["jsCode"]
    assert "$input.item.binary" in node(update, "Validate KB Upload")["parameters"]["jsCode"]
    assert node(update, "Qdrant Vector Store - Update Documents")["onError"] == "continueErrorOutput"
    assert "must_not" in node(update, "Delete Previous Source Versions")["parameters"]["body"]
    assert update["connections"]["Qdrant Vector Store - Update Documents"]["main"][0][0]["node"] == "Delete Previous Source Versions"
    assert ticket["connections"]["Classification Fallback"]["main"][0][0]["node"] == "route.by-classification.v1"
    fallback = node(ticket, "Classification Fallback")["parameters"]["jsCode"]
    assert "const base = $json" in fallback and "grounded_draft_reply" in fallback
    pdf_context = node(ticket, "Add PDF Context")["parameters"]["jsCode"]
    assert "rawExtracted.slice(0, 12000)" in pdf_context and "Untrusted PDF attachment text follows" in pdf_context
    assert "rag_min_score: 0.1" in node(ticket, "Validate and Normalize")["parameters"]["jsCode"]
    assert {"Receive Public Chat", "Validate Public Question", "Public RAG Vector Search", "Embeddings OpenAI - Public RAG", "Build MiniMax Request", "MiniMax Public RAG Chain", "MiniMax Chat Model - Public", "Build Public Chat Response", "Respond Public Chat"} <= names(public_chat)
    assert node(public_chat, "Receive Public Chat")["parameters"]["path"] == "noavia/public-chat/v1"
    assert node(public_chat, "Receive Public Chat")["parameters"]["authentication"] == "headerAuth"
    assert node(public_chat, "Public RAG Vector Search")["parameters"]["qdrantCollection"]["value"] == "noavia_public_chat_kb_v1"
    assert node(public_chat, "Public RAG Vector Search")["parameters"]["options"]["contentPayloadKey"] == "page_content"
    assert node(public_chat, "Embeddings OpenAI - Public RAG")["parameters"]["options"]["dimensions"] == 1536
    assert "untrusted data" in node(public_chat, "Build MiniMax Request")["parameters"]["jsCode"]
    assert node(public_chat, "MiniMax Chat Model - Public")["type"] == "@n8n/n8n-nodes-langchain.lmChatMinimax"
    assert node(public_chat, "MiniMax Chat Model - Public")["credentials"]["minimaxApi"]["name"] == "MiniMax account"
    assert node(public_chat, "MiniMax Public RAG Chain")["type"] == "@n8n/n8n-nodes-langchain.chainLlm"
    assert node(public_chat, "Respond Public Chat")["parameters"]["respondWith"] == "firstIncomingItem"
    assert "replace(/^```" in node(public_chat, "Build Public Chat Response")["parameters"]["jsCode"]
    assert node(admin_chat, "Admin RAG Vector Search")["parameters"]["options"]["contentPayloadKey"] == "page_content"
    assert node(admin_chat, "Respond Admin Chat")["parameters"]["respondWith"] == "firstIncomingItem"
    assert "replace(/^```" in node(admin_chat, "Build Admin Chat Response")["parameters"]["jsCode"]
    public_response = node(public_chat, "Build Public Chat Response")["parameters"]["jsCode"]
    assert "if (!matches.length)" in public_response and "ok:true" in public_response
    assert {"Receive Library Action", "Validate Library Action", "Qdrant Library Action", "Build Library Response", "Respond Library Action"} <= names(library)
    assert node(library, "Receive Library Action")["parameters"]["authentication"] == "headerAuth"
    validation = node(library, "Validate Library Action")["parameters"]["jsCode"]
    assert "noavia_kb_v1" in validation and "noavia_public_chat_kb_v1" in validation and "noavia_admin_kb_v1" in validation
    assert "['list','read','delete']" in validation
    assert "metadata.source" in validation
    assert {"Receive Document Mutation", "Validate Document Mutation", "Decode Source Document", "Qdrant Vector Store - Insert New Version", "Delete Older Vector Versions", "Save Canonical Source", "Delete Source Vectors", "Retire Canonical Source"} <= names(document_manager)
    manager_validation = node(document_manager, "Validate Document Mutation")["parameters"]["jsCode"]
    assert "noavia_kb_v1" in manager_validation and "noavia_public_chat_kb_v1" in manager_validation and "noavia_admin_kb_v1" in manager_validation
    assert node(document_manager, "Receive Document Mutation")["parameters"]["path"] == "noavia/documents/v1"
    assert node(document_manager, "Embeddings OpenAI - text-embedding-3-small")["parameters"]["options"]["dimensions"] == 1536
    version_cleanup = node(document_manager, "Delete Older Vector Versions")["parameters"]["jsCode"]
    assert "must_not" in version_cleanup and "httpRequest" in version_cleanup
    assert "A valid Markdown or text document" in manager_validation
    assert document_manager["connections"]["Qdrant Vector Store - Insert New Version"]["main"][0][0]["node"] == "Save Canonical Source"
    assert document_manager["connections"]["Save Canonical Source"]["main"][0][0]["node"] == "Delete Older Vector Versions"
    assert node(document_manager, "Save Canonical Source")["onError"] == "continueErrorOutput"
    assert node(document_manager, "Retire Canonical Source")["onError"] == "continueErrorOutput"
    assert node(document_manager, "Retire Canonical Source")["parameters"]["operation"] == "update"
    assert "index_status" in node(source_library, "Build Source Library Response")["parameters"]["jsCode"]
    assert {"Receive Source Library Read", "Read Canonical Sources", "Build Source Library Response"} <= names(source_library)
    assert node(source_library, "Receive Source Library Read")["parameters"]["path"] == "noavia/source-library/v1"
    assert "noavia_source_documents_v2" in node(source_library, "Read Canonical Sources")["parameters"]["dataTableId"]["value"]
    assert "Create NOAVIA Source Documents Table" in names(source_bootstrap)
    print(f"PASS: ticket={len(ticket['nodes'])} nodes; ingestion={len(ingest['nodes'])} nodes; kb-update={len(update['nodes'])} nodes; public-chat={len(public_chat['nodes'])} nodes; document-manager={len(document_manager['nodes'])} nodes; required Part 1 contracts present")


if __name__ == "__main__":
    main()
