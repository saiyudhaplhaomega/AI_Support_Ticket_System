#!/usr/bin/env python3
"""Offline contract checks for the importable NOAVIA n8n workflow."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow/noavia/workflow.noavia-ticket-pipeline.v1.json"


def run_code_node(js_code, payload, *, binary=None, node_data=None, env=None):
    """Execute an n8n Code-node body with only the globals used by this workflow."""
    harness = """
const code = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const binary = JSON.parse(process.argv[3]);
const nodeData = JSON.parse(process.argv[4]);
const environment = JSON.parse(process.argv[5]);
const lookup = (name) => ({ item: { json: nodeData[name] } });
const quietConsole = { log: () => {} };
const result = new Function('$json', '$binary', '$', '$env', 'console', code)(
  payload, binary, lookup, environment, quietConsole
);
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        [
            "node",
            "-e",
            harness,
            js_code,
            json.dumps(payload),
            json.dumps(binary or {}),
            json.dumps(node_data or {}),
            json.dumps(env or {}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_m1_hostile_rag_collection(nodes, validator, valid_payload) -> None:
    """M1 (a)+(c): a hostile config.rag_collection MUST be rejected.

    The plan requires the default allow-list to be ['noavia_kb_v1']. The
    classification service's AI_RAG_COLLECTION default is 'kb_documents'
    (services/classification/app/config.py:131). A payload that names
    'kb_documents' (or any collection not in the allow-list) must surface
    as VALIDATION_ERROR so the workflow cannot exfiltrate vectors from
    another collection.
    """
    for hostile_value in ("kb_documents", "internal_secrets", ""):
        payload = {**valid_payload, "config": {"rag_collection": hostile_value}}
        result = run_code_node(validator, payload)[0]["json"]
        assert result["ok"] is False, f"hostile rag_collection={hostile_value!r} should be rejected"
        assert result["error"]["code"] == "VALIDATION_ERROR"
        details_by_field = {d["field"]: d for d in result["error"]["details"]}
        assert "config.rag_collection" in details_by_field, (
            f"missing config.rag_collection error for value={hostile_value!r}; got fields: {list(details_by_field)}"
        )
        assert "not in allowlist" in details_by_field["config.rag_collection"]["message"]

    # Sanity: a payload with the allow-listed rag_collection MUST be accepted.
    accepted = run_code_node(validator, {**valid_payload, "config": {"rag_collection": "noavia_kb_v1"}})[0]["json"]
    assert accepted["ok"] is True
    assert accepted["config"]["rag_collection"] == "noavia_kb_v1"

    # Sanity: a payload with NO config MUST be accepted and use defaults.
    bare = run_code_node(validator, valid_payload)[0]["json"]
    assert bare["ok"] is True
    assert bare["config"]["sheet_name"] == "NOAVIA Support Tickets - Test"
    assert bare["config"]["top_k"] == 3
    assert bare["config"]["rag_min_score"] == 0.6


def test_m1_top_k_and_rag_filter(nodes, validator, valid_payload) -> None:
    """M1 (a): top_k clamps to 1..10; rag_filter shape is enforced.

    top_k outside the [1, 10] range MUST fall back to the default 3.
    A malformed rag_filter (string, array, or non-Qdrant shape) MUST be
    rejected with VALIDATION_ERROR. A well-formed rag_filter MUST be
    preserved as caller-supplied.
    """
    # top_k above the cap clamps to default 3.
    high = run_code_node(validator, {**valid_payload, "config": {"top_k": 15}})[0]["json"]
    assert high["ok"] is True and high["config"]["top_k"] == 3
    # top_k below the floor clamps to default 3.
    low = run_code_node(validator, {**valid_payload, "config": {"top_k": 0}})[0]["json"]
    assert low["ok"] is True and low["config"]["top_k"] == 3
    # top_k in range is preserved.
    kept = run_code_node(validator, {**valid_payload, "config": {"top_k": 7}})[0]["json"]
    assert kept["ok"] is True and kept["config"]["top_k"] == 7
    # top_k that is not a finite number clamps to default 3.
    nan = run_code_node(validator, {**valid_payload, "config": {"top_k": "NaN"}})[0]["json"]
    assert nan["ok"] is True and nan["config"]["top_k"] == 3

    # Malformed rag_filter shapes are rejected.
    for bad_filter in ("just-a-string", ["array", "shape"], {"unknown_key": "x"}, {"must": "not-an-array"}):
        bad = run_code_node(validator, {**valid_payload, "config": {"rag_filter": bad_filter}})[0]["json"]
        assert bad["ok"] is False, f"malformed rag_filter={bad_filter!r} should be rejected"
        fields = {d["field"] for d in bad["error"]["details"]}
        assert "config.rag_filter" in fields

    # A well-formed rag_filter is preserved.
    good_filter = {"must": [{"key": "source", "match": {"value": "kb"}}]}
    accepted = run_code_node(validator, {**valid_payload, "config": {"rag_filter": good_filter}})[0]["json"]
    assert accepted["ok"] is True
    assert accepted["config"]["rag_filter"] == good_filter

    # Undefined rag_filter is the no-op path.
    no_filter = run_code_node(validator, {**valid_payload, "config": {"top_k": 5}})[0]["json"]
    assert no_filter["ok"] is True
    assert "rag_filter" not in no_filter["config"]


def test_m2_fallback_distinction(nodes, valid_payload, trusted_routing) -> None:
    """M2 (a): Classification Fallback and RAG Fallback produce DISTINCT Sheet
    row values for status, error_code, and error_message.

    Per FINAL PLAN v6 §2.2 M2: the Sheet row already carries the
    distinction; if any surface was missing, a minimal mapping was added.
    The mapping differentiates error_code by inspecting processing_error.message
    so upstream-provided codes pass through unchanged.
    """
    # Build the post-Validate base the fallback nodes consume.
    ingested = {
        **valid_payload,
        "ticket": {
            "id": valid_payload["ticket_id"],
            "requester_name": "Test Customer",
            "subject": valid_payload["subject"],
            "body": valid_payload["body"],
            "text": f"{valid_payload['subject']}\n\n{valid_payload['body']}",
            "requester_email": valid_payload["requester_email"],
            "locale": "en",
            "received_at": "2026-08-16T00:00:00.000Z",
            "attachment_name": None,
        },
        "context": {},
        "config": {"sheet_name": "NOAVIA Support Tickets - Test", "top_k": 3, "rag_min_score": 0.6},
        "correlation_id": "corr-fallback",
        "audit_logs": [],
    }
    classification_fallback_js = nodes["Classification Fallback"]["parameters"]["jsCode"]
    rag_fallback_js = nodes["RAG Fallback"]["parameters"]["jsCode"]
    route_js = nodes["route.by-classification.v1"]["parameters"]["jsCode"]

    # --- Classification Fallback: feeds $json.error (from upstream node). ---
    cf_input = {**ingested, "error": {"code": "UPSTREAM_ERROR", "message": "Classification failed"}}
    cf_after = run_code_node(
        classification_fallback_js, cf_input,
        node_data={"audit.ingestion.v1": ingested},
    )[0]["json"]
    assert cf_after["processing_status"] == "needs-manual-review"
    cf_routed = run_code_node(route_js, {**cf_after, "grounded_draft_reply": {"text": "fallback reply"}}, env=trusted_routing)[0]["json"]
    cf_row = cf_routed["sheet_row"]

    # --- RAG Fallback: feeds $json.error (from upstream node). ---
    # Prepare RAG Lookup is the node right before ai.rag-lookup.v1; its output
    # already carries classification (which succeeded; only RAG failed). The
    # fallback uses that as `base` and overrides rag_matches/etc.
    prepare_rag_lookup_output = {**ingested, "classification": {"category": "billing", "confidence": 0.87, "tags": ["duplicate_charge"]}, "processing_status": "routed"}
    rf_input = {
        **ingested,
        "classification": {"category": "billing", "confidence": 0.87, "tags": ["duplicate_charge"]},
        "processing_status": "routed",
        "error": {"code": "UPSTREAM_ERROR", "message": "RAG lookup failed"},
    }
    rf_after = run_code_node(
        rag_fallback_js, rf_input,
        node_data={"Prepare RAG Lookup": prepare_rag_lookup_output},
    )[0]["json"]
    assert rf_after["processing_status"] == "routed_without_rag"
    assert rf_after["classification"]["category"] == "billing"
    rf_routed = run_code_node(route_js, {**rf_after, "grounded_draft_reply": {"text": "fallback reply"}}, env=trusted_routing)[0]["json"]
    rf_row = rf_routed["sheet_row"]

    # The Sheet row must distinguish the two paths on all three surfaces.
    assert cf_row["status"] != rf_row["status"], (
        f"status must differ; cf={cf_row['status']!r}, rf={rf_row['status']!r}"
    )
    assert cf_row["status"] == "needs-manual-review"
    assert rf_row["status"] == "routed_without_rag"
    assert cf_row["error_code"] != rf_row["error_code"], (
        f"error_code must differ; cf={cf_row['error_code']!r}, rf={rf_row['error_code']!r}"
    )
    assert cf_row["error_message"] != rf_row["error_message"], (
        f"error_message must differ; cf={cf_row['error_message']!r}, rf={rf_row['error_message']!r}"
    )
    assert "Classification" in cf_row["error_message"]
    assert "RAG" in rf_row["error_message"]


def main() -> None:
    data = json.loads(WORKFLOW.read_text())
    assert data["name"] == "workflow.noavia-ticket-pipeline.v1" and data["active"] is False
    nodes = {node["name"]: node for node in data["nodes"]}
    required = {
        "Ingest Support Ticket",
        "Validate and Normalize",
        "audit.ingestion.v1",
        "Validation OK?",
        "audit.validation-rejection.v1",
        "Respond Validation Error",
        "Has PDF Attachment?",
        "Extract PDF Text",
        "ai.classify-ticket.v1",
        "Classification OK?",
        "ai.rag-lookup.v1",
        "RAG Lookup OK?",
        "Classification Fallback",
        "RAG Fallback",
        "draft.grounded-reply.v1",
        "route.by-classification.v1",
        "notify.google-sheets.v1",
        "notify.routing-email.v1",
        "audit.delivery-outcome.v1",
        "Respond Processing Result",
    }
    assert not (required - nodes.keys()), f"missing nodes: {required - nodes.keys()}"
    for node in data["nodes"]:
        if node["type"] == "n8n-nodes-base.code":
            subprocess.run(
                ["node", "-e", "new Function(process.argv[1])", node["parameters"]["jsCode"]],
                check=True,
                capture_output=True,
                text=True,
            )

    classify, rag = nodes["ai.classify-ticket.v1"]["parameters"], nodes["ai.rag-lookup.v1"]["parameters"]
    assert classify["url"].endswith("/ai/classify-ticket/v1") and rag["url"].endswith("/ai/rag-lookup/v1")
    for request in (classify, rag):
        headers = {h["name"]: h["value"] for h in request["headerParameters"]["parameters"]}
        assert "AI_CLASSIFY_API_KEY" in headers["Authorization"]
        assert headers["X-Correlation-Id"] == "={{ $json.correlation_id }}"
        assert request["options"]["response"]["response"]["neverError"] is True

    graph = data["connections"]
    for branch in ("Validation OK?", "Has PDF Attachment?", "Classification OK?", "RAG Lookup OK?"):
        assert len(graph[branch]["main"]) == 2
    assert graph["Validate and Normalize"]["main"][0][0]["node"] == "audit.ingestion.v1"
    assert graph["audit.ingestion.v1"]["main"][0][0]["node"] == "Validation OK?"
    assert graph["Validation OK?"]["main"][0][0]["node"] == "Has PDF Attachment?"
    assert graph["Validation OK?"]["main"][1][0]["node"] == "audit.validation-rejection.v1"
    assert graph["audit.validation-rejection.v1"]["main"][0][0]["node"] == "Respond Validation Error"
    for outcome in ("Attach RAG Matches", "RAG Fallback", "Classification Fallback"):
        assert graph[outcome]["main"][0][0]["node"] == "draft.grounded-reply.v1"
    assert graph["draft.grounded-reply.v1"]["main"][0][0]["node"] == "route.by-classification.v1"

    webhook = nodes["Ingest Support Ticket"]["parameters"]
    assert webhook["responseMode"] == "responseNode"
    validation_response = nodes["Respond Validation Error"]["parameters"]
    assert validation_response["options"]["responseCode"] == 400
    assert "error: $json.error" in validation_response["responseBody"]

    validator = nodes["Validate and Normalize"]["parameters"]["jsCode"]
    assert "throw new Error" not in validator
    invalid = run_code_node(validator, {"subject": "", "correlation_id": "corr-invalid"})[0]["json"]
    assert invalid["ok"] is False and invalid["error"]["code"] == "VALIDATION_ERROR"
    assert {x["field"] for x in invalid["error"]["details"]} == {"requester_name", "subject", "body", "requester_email"}
    valid_payload = {
        "ticket_id": "NVA-1",
        "requester_name": "Test Customer",
        "subject": "Charged twice",
        "body": "Duplicate charge",
        "requester_email": "customer@example.com",
        "correlation_id": "corr-valid",
    }
    valid = run_code_node(validator, valid_payload)[0]["json"]
    assert valid["ok"] is True and valid["ticket"]["id"] == "NVA-1"
    assert valid["correlation_id"] == "corr-valid"

    invalid_pdf = run_code_node(
        validator,
        valid_payload,
        binary={"data": {"mimeType": "text/plain", "fileName": "notes.txt", "fileSize": 20}},
    )[0]["json"]
    assert invalid_pdf["ok"] is False
    assert {detail["message"] for detail in invalid_pdf["error"]["details"]} == {"attachment must be a PDF"}
    oversized_pdf = run_code_node(
        validator,
        valid_payload,
        binary={"data": {"mimeType": "application/pdf", "fileName": "ticket.pdf", "fileSize": 10 * 1024 * 1024 + 1}},
    )[0]["json"]
    assert oversized_pdf["ok"] is False
    assert {detail["message"] for detail in oversized_pdf["error"]["details"]} == {"PDF exceeds 10 MB"}

    pdf_context = run_code_node(
        nodes["Add PDF Context"]["parameters"]["jsCode"],
        {"text": "The attached invoice has two August charges."},
        node_data={"audit.ingestion.v1": valid},
    )[0]["json"]
    assert pdf_context["ticket"]["text"].endswith("PDF attachment:\nThe attached invoice has two August charges.")
    pdf_empty_fallback = run_code_node(
        nodes["Add PDF Context"]["parameters"]["jsCode"],
        {"text": "  "},
        node_data={"audit.ingestion.v1": valid},
    )[0]["json"]
    assert pdf_empty_fallback["ticket"]["text"] == valid["ticket"]["text"]

    audit_nodes = (
        "audit.ingestion.v1",
        "audit.validation-rejection.v1",
        "Classification Fallback",
        "RAG Fallback",
        "audit.delivery-outcome.v1",
    )
    required_log_fields = ("ts", "module", "interface_id", "version", "correlation_id", "level", "message")
    for name in audit_nodes:
        code = nodes[name]["parameters"]["jsCode"]
        for field in required_log_fields:
            assert f"{field}:" in code, f"{name} missing audit field {field}"
        assert "console.log(JSON.stringify(record" in code or "console.log(JSON.stringify(record))" in code

    ingested = run_code_node(
        nodes["audit.ingestion.v1"]["parameters"]["jsCode"],
        {"ok": True, "correlation_id": "corr-log", "audit_logs": []},
    )[0]["json"]
    record = ingested["audit_logs"][0]
    assert set(required_log_fields) <= record.keys()
    assert record["correlation_id"] == "corr-log" and record["level"] == "info"

    route_base = {
        "ticket": {"id": "NVA-1"},
        "route": {"queue": "billing"},
        "processing_status": "routed",
        "correlation_id": "corr-delivery",
        "audit_logs": [record],
    }
    delivery = run_code_node(
        nodes["audit.delivery-outcome.v1"]["parameters"]["jsCode"],
        {"accepted": []},
        node_data={
            "route.by-classification.v1": route_base,
            "notify.google-sheets.v1": {"error": {"code": "SHEETS_DOWN", "message": "unavailable"}},
        },
    )[0]["json"]
    assert delivery["ok"] is False
    assert delivery["error"]["code"] == "DELIVERY_ERROR"
    assert delivery["error"]["details"][0]["target"] == "google_sheets"
    assert delivery["audit_logs"][-1]["level"] == "error"
    assert delivery["audit_logs"][-1]["correlation_id"] == "corr-delivery"

    route_input = {
        **valid,
        "classification": {"category": "billing", "confidence": 0.87, "tags": ["duplicate_charge", "refund"]},
        "rag_matches": [
            {"score": 0.9234, "content": "Use the duplicate-charge refund policy.", "metadata": {"source": "kb/duplicate-charge"}},
            {"score": 0.8123, "content": "Ask for the transaction dates.", "metadata": {"source": "kb/billing"}},
        ],
        "processing_status": "routed",
        "processing_error": None,
    }
    trusted_routing = {"NOAVIA_NOTIFY_ROUTE_ALLOWLIST_JSON": json.dumps({"default": "support@example.com", "billing": "billing@example.com", "manual_review": "support-lead@example.com"})}
    attached = run_code_node(nodes["Attach RAG Matches"]["parameters"]["jsCode"], {"data": {"matches": route_input["rag_matches"]}}, node_data={"Prepare RAG Lookup": route_input})[0]["json"]
    # Drafting remains an internal-only workflow value; it is never connected
    # to a customer-facing email node.
    draft_node = nodes["draft.grounded-reply.v1"]
    assert draft_node["type"] == "n8n-nodes-base.code"
    assert "No specific policy found" in draft_node["parameters"]["jsCode"]
    assert "top_k: $json.config.top_k" in nodes["ai.rag-lookup.v1"]["parameters"]["body"]
    drafted = {**attached, "grounded_draft_reply": {"text": "Grounded reply [1] kb/duplicate-charge", "citations": attached["knowledge_sources"]}}
    routed = run_code_node(nodes["route.by-classification.v1"]["parameters"]["jsCode"], drafted, env=trusted_routing)[0]["json"]
    low_attached = run_code_node(nodes["Attach RAG Matches"]["parameters"]["jsCode"], {"data": {"matches": [{"score": 0.59, "content": "Unverified guidance", "metadata": {"source": "kb/unverified"}}]}}, node_data={"Prepare RAG Lookup": route_input})[0]["json"]
    assert low_attached["rag_below_threshold"] is True
    expected_sheet_columns = [
        "received_at", "ticket_id", "correlation_id", "requester_email", "subject", "category",
        "confidence", "tags", "route_queue", "route_email", "status", "attachment_name",
        "rag_match_count", "rag_context", "error_code", "error_message",
    ]
    assert list(routed["sheet_row"]) == expected_sheet_columns
    assert routed["route"] == {"queue": "billing", "email": "billing@example.com"}
    assert routed["sheet_row"]["confidence"] == 0.87
    assert routed["sheet_row"]["rag_match_count"] == 2
    assert "[0.923] Use the duplicate-charge refund policy." in routed["sheet_row"]["rag_context"]
    assert "Correlation ID: corr-valid" in routed["notification_text"]
    assert "kb/duplicate-charge" in routed["grounded_draft_reply"]["text"]

    sheets_columns = nodes["notify.google-sheets.v1"]["parameters"]["columns"]["value"]
    assert list(sheets_columns) == expected_sheet_columns
    assert all(value == "={{ $json.sheet_row." + column + " }}" for column, value in sheets_columns.items())

    raw = WORKFLOW.read_text()
    assert not any(value in raw for value in ("sk-", "AIza", "smtp.gmail.com"))
    assert "manual_review" in nodes["Classification Fallback"]["parameters"]["jsCode"]
    assert "confidence < 0.6" in nodes["route.by-classification.v1"]["parameters"]["jsCode"]
    assert "rag_min_score ?? 0.6" in nodes["Attach RAG Matches"]["parameters"]["jsCode"]
    assert nodes["draft.grounded-reply.v1"]["type"] == "n8n-nodes-base.code"
    assert nodes["notify.google-sheets.v1"]["onError"] == "continueRegularOutput"
    assert nodes["notify.routing-email.v1"]["onError"] == "continueRegularOutput"
    sheets = nodes["notify.google-sheets.v1"]
    assert sheets["parameters"]["operation"] == "append"
    assert sheets["credentials"]["googleSheetsOAuth2Api"]["name"] == "Google Sheets account"
    header = nodes["initialize.google-sheets-header.v1"]
    assert header["disabled"] is True
    assert list(header["parameters"]["columns"]["value"]) == expected_sheet_columns
    email_node = nodes["notify.routing-email.v1"]
    assert email_node["type"] == "n8n-nodes-base.gmail"
    assert email_node["credentials"] == {"gmailOAuth2": {"id": "", "name": ""}}
    assert email_node["parameters"]["sendTo"] == "={{ $(\"route.by-classification.v1\").item.json.route.email }}"
    assert "from" not in email_node["parameters"]

    # Regression: untrusted request fields cannot influence Gmail addressing.
    hostile_payload = {**valid_payload, "from_email": "attacker-from@example.net", "default_route_email": "attacker-default@example.net", "routing_emails": {"billing": "attacker-route@example.net"}, "config": {"from_email": "attacker-from@example.net", "default_route_email": "attacker-default@example.net", "routing_emails": {"billing": "attacker-route@example.net"}}}
    hostile = run_code_node(validator, hostile_payload)[0]["json"]
    hostile_routed = run_code_node(nodes["route.by-classification.v1"]["parameters"]["jsCode"], {**hostile, "classification": {"category": "billing", "confidence": 0.9, "tags": []}, "rag_matches": [], "processing_status": "routed"}, env=trusted_routing)[0]["json"]
    assert hostile_routed["route"]["email"] == "billing@example.com"

    # ---- M1 hostile-input: hostile rag_collection MUST be REJECTED. ----
    test_m1_hostile_rag_collection(nodes, validator, valid_payload)
    # ---- M1 hardening: top_k clamps to 1..10; rag_filter shape is enforced. ----
    test_m1_top_k_and_rag_filter(nodes, validator, valid_payload)
    # ---- M2 fallback distinction: Sheet row distinguishes both paths. ----
    test_m2_fallback_distinction(nodes, valid_payload, trusted_routing)
    print(f"PASS: {len(nodes)} nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present")


if __name__ == "__main__":
    main()