#!/usr/bin/env python3
"""Credential-free evaluation of the NOAVIA deterministic local RAG baseline."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "classification"))
from app.local_rag import DeterministicHashEmbedder, InMemoryVectorStore, ingest_directory, retrieve

CASES=ROOT/"evals/noavia_rag_eval.jsonl"; OUT=ROOT/"evals/noavia_rag_eval_results.json"
def source(match): return Path(str(match.metadata.get("source", ""))).name
def main():
 e=DeterministicHashEmbedder(); s=InMemoryVectorStore(); ingest_directory(ROOT/"knowledge-base/noavia",e,s)
 rows=[]
 for c in map(json.loads, CASES.read_text().splitlines()):
  r=retrieve(c["query"],e,s,threshold=.10); got=[source(m) for m in r.matches]; expected=c["expected_source_filenames"]
  rank=next((i+1 for i,x in enumerate(got) if x in expected),None)
  rows.append({**c,"returned_sources":got,"scores":[m.score for m in r.matches],"fallback":r.low_confidence,"rank":rank})
 supported=[x for x in rows if not x["expected_fallback"]]; unsupported=[x for x in rows if x["expected_fallback"]]
 metrics={"case_count":len(rows),"recall_at_3":sum(x["rank"] is not None for x in supported)/len(supported),"top_1_accuracy":sum(x["rank"]==1 for x in supported)/len(supported),"mrr":sum(1/x["rank"] if x["rank"] else 0 for x in supported)/len(supported),"unsupported_fallback_accuracy":sum(x["fallback"] for x in unsupported)/len(unsupported),"false_confidence_cases":[x["id"] for x in unsupported if not x["fallback"]],"supported_top_score_mean":sum(x["scores"][0] if x["scores"] else 0 for x in supported)/len(supported),"unsupported_top_score_mean":sum(x["scores"][0] if x["scores"] else 0 for x in unsupported)/len(unsupported),"threshold":.10}
 OUT.write_text(json.dumps({"metrics":metrics,"cases":rows},indent=2)+"\n")
 print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()
