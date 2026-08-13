#!/usr/bin/env python3
"""Offline contract checks for the importable NOAVIA n8n workflow."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow/noavia/workflow.noavia-ticket-pipeline.v1.json"


def run_code_node(js_code, payload, *, binary=None, node_data=None):
    """Execute an n8n Code-node body with only the globals used by this workflow."""
    harness = """
const code = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const binary = JSON.parse(process.argv[3]);
const nodeData = JSON.parse(process.argv[4]);
const lookup = (name) => ({ item: { json: nodeData[name] } });
const quietConsole = { log: () => {} };
const result = new Function('$json', '$binary', '$', 'console', code)(
  payload, binary, lookup, quietConsole
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
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


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
        assert graph[outcome]["main"][0][0]["node"] == "route.by-classification.v1"

    webhook = nodes["Ingest Support Ticket"]["parameters"]
    assert webhook["responseMode"] == "responseNode"
    validation_response = nodes["Respond Validation Error"]["parameters"]
    assert validation_response["options"]["responseCode"] == 400
    assert "error: $json.error" in validation_response["responseBody"]

    validator = nodes["Validate and Normalize"]["parameters"]["jsCode"]
    assert "throw new Error" not in validator
    invalid = run_code_node(validator, {"subject": "", "correlation_id": "corr-invalid"})[0]["json"]
    assert invalid == {
        "ok": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Ticket validation failed",
            "details": [
                {"field": "subject", "message": "subject is required"},
                {"field": "body", "message": "body is required"},
                {"field": "requester_email", "message": "requester_email is required"},
                {"field": "config.sheet_id", "message": "config.sheet_id is required"},
                {"field": "config.sheet_name", "message": "config.sheet_name is required"},
                {"field": "config.default_route_email", "message": "config.default_route_email is required"},
                {"field": "config.from_email", "message": "config.from_email is required"},
            ],
        },
        "correlation_id": "corr-invalid",
        "audit_logs": [],
    }
    valid_payload = {
        "ticket_id": "NVA-1",
        "subject": "Charged twice",
        "body": "Duplicate charge",
        "requester_email": "customer@example.com",
        "correlation_id": "corr-valid",
        "config": {
            "sheet_id": "sheet",
            "sheet_name": "Tickets",
            "default_route_email": "support@example.com",
            "from_email": "noavia@example.com",
        },
    }
    valid = run_code_node(validator, valid_payload)[0]["json"]
    assert valid["ok"] is True and valid["ticket"]["id"] == "NVA-1"
    assert valid["correlation_id"] == "corr-valid"

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

    raw = WORKFLOW.read_text()
    assert not any(value in raw for value in ("sk-", "AIza", "smtp.gmail.com"))
    assert "manual_review" in nodes["Classification Fallback"]["parameters"]["jsCode"]
    assert nodes["notify.google-sheets.v1"]["onError"] == "continueRegularOutput"
    assert nodes["notify.routing-email.v1"]["onError"] == "continueRegularOutput"
    print(f"PASS: {len(nodes)} nodes; validation envelope, audit telemetry, fallbacks, and delivery contracts present")


if __name__ == "__main__":
    main()
