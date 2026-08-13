"""Offline/bulk ingestion CLI — the other half of `POST /internal/ingest/v1`.

Usage (run inside the container or a venv with this package's deps):

    python -m app.ingest_cli --file kb.jsonl --collection kb_documents

Input file is JSON Lines, one document per line:

    {"id": "kb-42", "content": "How to reset your password...", "metadata": {"source": "kb"}}

`id` and `metadata` are optional. Reads the same env vars as the HTTP
service (OPENAI_API_KEY, QDRANT_URL, ...) — see .env.example.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from app.clients.openai_client import get_openai_client
from app.clients.qdrant_client import get_qdrant_client
from app.config import load_settings_or_exit
from app.errors import ModuleError
from app.schemas import IngestRecord
from app.services.ingest_service import ingest_documents


def _load_records(path: str) -> list[IngestRecord]:
    records: list[IngestRecord] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON — {exc}") from exc
            records.append(IngestRecord(**raw))
    return records


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings_or_exit()
    records = _load_records(args.file)
    if not records:
        print(f"No records found in {args.file}", file=sys.stderr)
        return 1

    openai_client = get_openai_client(settings)
    qdrant_client = get_qdrant_client(settings)
    correlation_id = str(uuid.uuid4())

    try:
        result = await ingest_documents(
            openai_client, qdrant_client, settings, records, args.collection, correlation_id
        )
    except ModuleError as exc:
        print(f"Ingestion failed [{exc.code.value}]: {exc.message}", file=sys.stderr)
        return 1
    finally:
        await qdrant_client.close()

    print(f"Ingested {result.ingested} record(s) into '{result.collection}' (correlation_id={correlation_id})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to a JSONL file of documents to ingest.")
    parser.add_argument(
        "--collection", default=None, help="Target Qdrant collection (defaults to AI_RAG_COLLECTION)."
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
