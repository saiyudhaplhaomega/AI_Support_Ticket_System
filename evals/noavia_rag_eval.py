#!/usr/bin/env python3
"""Run NOAVIA's credential-free retrieval evaluation and write JSON results."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "classification"))

from app.local_rag import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    DeterministicHashEmbedder,
    InMemoryVectorStore,
    ingest_directory,
    retrieve,
)


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(cases: list[dict], threshold: float) -> dict:
    embedder, store = DeterministicHashEmbedder(), InMemoryVectorStore()
    ingest_directory(ROOT / "knowledge-base" / "noavia", embedder, store)
    rows = []
    for case in cases:
        result = retrieve(case["query"], embedder, store, top_k=3, threshold=threshold)
        sources = [match.metadata["source"] for match in result.matches]
        expected = set(case["expected_sources"])
        first_rank = next((i + 1 for i, source in enumerate(sources) if source in expected), None)
        rows.append({
            "id": case["id"], "expected_fallback": case["expected_fallback"],
            "expected_sources": case["expected_sources"], "sources": sources,
            "scores": [round(match.score, 6) for match in result.matches],
            "fallback": result.low_confidence, "first_relevant_rank": first_rank,
            "passed": (result.low_confidence == case["expected_fallback"] and
                       (case["expected_fallback"] or first_rank is not None)),
        })
    supported = [row for row in rows if not row["expected_fallback"]]
    unsupported = [row for row in rows if row["expected_fallback"]]
    recall = sum(row["first_relevant_rank"] is not None for row in supported) / len(supported)
    top1 = sum(row["first_relevant_rank"] == 1 for row in supported) / len(supported)
    mrr = sum(1 / row["first_relevant_rank"] if row["first_relevant_rank"] else 0 for row in supported) / len(supported)
    unsupported_accuracy = sum(row["fallback"] for row in unsupported) / len(unsupported)
    false_confidence = [row["id"] for row in unsupported if not row["fallback"]]
    def top_scores(items: list[dict]) -> list[float]:
        return [row["scores"][0] if row["scores"] else 0.0 for row in items]
    return {"threshold": threshold, "case_count": len(rows), "metrics": {
        "recall_at_3": round(recall, 4), "top_1_accuracy": round(top1, 4),
        "mean_reciprocal_rank": round(mrr, 4),
        "unsupported_fallback_accuracy": round(unsupported_accuracy, 4),
        "false_confidence_cases": false_confidence,
        "supported_top_score_distribution": _distribution(top_scores(supported)),
        "unsupported_top_score_distribution": _distribution(top_scores(unsupported)),
    }, "cases": rows}


def _distribution(scores: list[float]) -> dict:
    ordered = sorted(scores)
    return {"min": round(ordered[0], 6), "median": round(statistics.median(ordered), 6),
            "max": round(ordered[-1], 6), "mean": round(sum(ordered)/len(ordered), 6)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "noavia_rag_eval.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "noavia_rag_eval_results.json")
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    args = parser.parse_args()
    report = evaluate(load_cases(args.cases), args.threshold)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
