#!/usr/bin/env python3
"""Credential-free acceptance checks for the current NOAVIA Part 1 exports.

The former test exercised the retired classification-service contract. It is
preserved as ``test_noavia_workflow.legacy.py``; this test validates the
direct-OpenAI/native-Qdrant Part 1 submission and needs no Node.js runtime.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TICKET = ROOT / "workflow/noavia/workflow.noavia-ticket-pipeline.v1.json"
INGEST = ROOT / "workflow/noavia/workflow.noavia-kb-ingestion.v1.json"
UPDATE = ROOT / "workflow/noavia/workflow.noavia-kb-webhook-update.v1.json"


class NoaviaWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ticket = json.loads(TICKET.read_text(encoding="utf-8"))
        cls.ingest = json.loads(INGEST.read_text(encoding="utf-8"))
        cls.update = json.loads(UPDATE.read_text(encoding="utf-8"))
        cls.nodes = {node["name"]: node for node in cls.ticket["nodes"]}

    def test_part1_node_graph(self) -> None:
        required = {
            "Ingest Support Ticket", "Validate and Normalize", "Extract PDF Text",
            "build.classify-prompt.v1", "ai.classify-ticket.v1", "parse.classify-response.v1",
            "RAG Vector Search", "Embeddings OpenAI (RAG)", "Collect RAG Matches",
            "build.draft-prompt.v1", "ai.draft-response.v1", "parse.draft-response.v1",
            "route.by-classification.v1", "notify.google-sheets.v1", "notify.routing-email.v1",
        }
        self.assertTrue(required <= set(self.nodes), required - set(self.nodes))

    def test_required_intake_and_pdf_parallelism(self) -> None:
        validator = self.nodes["Validate and Normalize"]["parameters"]["jsCode"]
        self.assertIn("required(input.requester_name ?? input.name, 'requester_name')", validator)
        self.assertNotIn("auto-derive requester_name", validator)
        pdf_targets = self.ticket["connections"]["Has PDF Attachment?"]["main"][0]
        self.assertEqual({edge["node"] for edge in pdf_targets}, {"notify.google-drive.v1", "Extract PDF Text"})
        self.assertEqual(self.ticket["connections"]["Extract PDF Text"]["main"][0][0]["node"], "join.pdf-branches.v1")

    def test_ai_rag_and_draft_contracts(self) -> None:
        self.assertEqual(self.nodes["Embeddings OpenAI (RAG)"]["parameters"]["model"], "text-embedding-3-small")
        self.assertEqual(self.nodes["RAG Vector Search"]["parameters"]["topK"], "={{ $json.config.top_k }}")
        classifier = self.nodes["parse.classify-response.v1"]["parameters"]["jsCode"]
        self.assertIn("Model output did not match the required schema", classifier)
        self.assertIn("ok: true", classifier)
        self.assertIn("envelope.statusCode", classifier)
        self.assertIn("...base, ok: false", classifier)
        self.assertIn("attachment_is_invoice", classifier)
        self.assertIn("attachment_invoice_reason", classifier)
        classify = self.nodes["ai.classify-ticket.v1"]
        self.assertEqual(classify["type"], "n8n-nodes-base.openAi")
        self.assertEqual(classify["parameters"]["resource"], "chat")
        self.assertEqual(classify["parameters"]["operation"], "complete")
        self.assertIn("model", classify["parameters"])
        self.assertTrue(classify["parameters"]["simplifyOutput"])
        self.assertIn("response.message?.content", classifier)
        self.assertLess(classifier.index("try {"), classifier.index("JSON.parse(rawContent)"))
        draft = self.nodes["build.draft-prompt.v1"]["parameters"]["jsCode"]
        self.assertIn("No specific policy found — this response is based on general knowledge.", draft)

    def test_routing_and_sheet_contract(self) -> None:
        route = self.nodes["route.by-classification.v1"]["parameters"]["jsCode"]
        self.assertIn("needs-manual-review", route)
        self.assertIn("queue_label: display(category)", route)
        subject = self.nodes["notify.routing-email.v1"]["parameters"]["subject"]
        self.assertIn("route.queue_label", subject)
        self.assertNotIn("route.queue +", subject)
        columns = self.nodes["notify.google-sheets.v1"]["parameters"]["columns"]["value"]
        required = {"ticket_id", "timestamp", "name", "email", "subject", "category", "urgency", "sentiment", "confidence", "ai_summary", "draft_response", "knowledge_sources", "status", "processing_log", "attachment_drive_link"}
        self.assertTrue(required <= set(columns), required - set(columns))
        schema = self.nodes["notify.google-sheets.v1"]["parameters"]["columns"]["schema"]
        self.assertTrue(required <= {field["id"] for field in schema})
        self.assertIn("PDF attachment: ${row.attachment_drive_link}", route)
        self.assertIn("This PDF does not appear to be an invoice", route)
        self.assertIn("Attachment check: ${row.invoice_check}", route)
        self.assertEqual(
            self.ticket["connections"]["Classification Fallback"]["main"][0][0]["node"],
            "route.by-classification.v1",
        )
        fallback = self.nodes["Classification Fallback"]["parameters"]["jsCode"]
        self.assertIn("const base = $json", fallback)
        self.assertIn("grounded_draft_reply", fallback)
        pdf_context = self.nodes["Add PDF Context"]["parameters"]["jsCode"]
        self.assertIn("rawExtracted.slice(0, 12000)", pdf_context)
        self.assertIn("Untrusted PDF attachment text follows", pdf_context)
        self.assertIn("rag_min_score: 0.1", self.nodes["Validate and Normalize"]["parameters"]["jsCode"])

    def test_ingestion_contract(self) -> None:
        nodes = {node["name"]: node for node in self.ingest["nodes"]}
        self.assertIn("Recursive Character Text Splitter - 800/120", nodes)
        embeddings = nodes["Embeddings OpenAI - text-embedding-3-small"]["parameters"]
        self.assertEqual(embeddings["model"], "text-embedding-3-small")
        self.assertEqual(embeddings["options"]["dimensions"], 1536)

    def test_frontend_kb_update_webhook_contract(self) -> None:
        nodes = {node["name"]: node for node in self.update["nodes"]}
        self.assertEqual(nodes["Receive KB Update"]["parameters"]["path"], "noavia/kb/update/v1")
        self.assertEqual(nodes["Receive KB Update"]["parameters"]["authentication"], "headerAuth")
        self.assertIn("Only .md, .markdown, and .txt", nodes["Validate KB Upload"]["parameters"]["jsCode"])
        self.assertIn("5 * 1024 * 1024", nodes["Validate KB Upload"]["parameters"]["jsCode"])
        self.assertNotIn("Buffer.from", nodes["Validate KB Upload"]["parameters"]["jsCode"])
        self.assertIn("Number.parseInt", nodes["Validate KB Upload"]["parameters"]["jsCode"])
        self.assertIn("$input.item.binary", nodes["Validate KB Upload"]["parameters"]["jsCode"])
        self.assertEqual(nodes["Embeddings OpenAI - text-embedding-3-small"]["parameters"]["options"]["dimensions"], 1536)
        self.assertEqual(nodes["Qdrant Vector Store - Update Documents"]["parameters"]["qdrantCollection"]["value"], "noavia_kb_v1")
        self.assertIn("Delete Previous Source Versions", nodes)
        self.assertIn("must_not", nodes["Delete Previous Source Versions"]["parameters"]["body"])
        self.assertEqual(self.update["connections"]["Qdrant Vector Store - Update Documents"]["main"][0][0]["node"], "Delete Previous Source Versions")
        self.assertEqual(nodes["Qdrant Vector Store - Update Documents"]["onError"], "continueErrorOutput")

    def test_ticket_export_builder_is_idempotent(self) -> None:
        builder = ROOT / "scripts/build_workflow.py"
        subprocess.run([sys.executable, str(builder)], cwd=ROOT, check=True, capture_output=True, text=True)
        first = TICKET.read_bytes()
        subprocess.run([sys.executable, str(builder)], cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertEqual(first, TICKET.read_bytes())


if __name__ == "__main__":
    unittest.main()
