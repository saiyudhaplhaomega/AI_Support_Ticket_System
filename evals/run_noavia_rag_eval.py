#!/usr/bin/env python3
"""Credential-free evaluation of the NOAVIA deterministic local RAG baseline."""
from __future__ import annotations
import json, sys
from pathlib import Path
from statistics import median
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "classification"))
from app.local_rag import DeterministicHashEmbedder, InMemoryVectorStore, ingest_directory, retrieve

CASES=ROOT/"evals/noavia_rag_eval.jsonl"; OUT=ROOT/"evals/noavia_rag_eval_results.json"
def source(match): return Path(str(match.metadata.get("source", ""))).name
def source_path(match): return str(match.metadata.get("source", ""))
def distribution(values):
 values=sorted(values)
 return {"min":round(values[0],6),"median":round(median(values),6),"max":round(values[-1],6),"mean":round(sum(values)/len(values),6)}
def main():
 e=DeterministicHashEmbedder(); s=InMemoryVectorStore(); ingest_directory(ROOT/"knowledge-base/noavia",e,s)
 rows=[]
 for c in map(json.loads, CASES.read_text().splitlines()):
  r=retrieve(c["query"],e,s,threshold=.10); got=[source(m) for m in r.matches]; expected=[Path(item).name for item in c["expected_sources"]]
  rank=next((i+1 for i,x in enumerate(got) if x in expected),None)
  rows.append({"id":c["id"],"expected_fallback":c["expected_fallback"],"expected_sources":c["expected_sources"],"sources":[source_path(m) for m in r.matches],"scores":[round(m.score,6) for m in r.matches],"fallback":r.low_confidence,"first_relevant_rank":rank,"passed":(r.low_confidence if c["expected_fallback"] else rank is not None)})
 supported=[x for x in rows if not x["expected_fallback"]]; unsupported=[x for x in rows if x["expected_fallback"]]
 metrics={"recall_at_3":round(sum(x["first_relevant_rank"] is not None for x in supported)/len(supported),4),"top_1_accuracy":round(sum(x["first_relevant_rank"]==1 for x in supported)/len(supported),4),"mean_reciprocal_rank":round(sum(1/x["first_relevant_rank"] if x["first_relevant_rank"] else 0 for x in supported)/len(supported),4),"unsupported_fallback_accuracy":round(sum(x["fallback"] for x in unsupported)/len(unsupported),4),"false_confidence_cases":[x["id"] for x in unsupported if not x["fallback"]],"supported_top_score_distribution":distribution([x["scores"][0] if x["scores"] else 0 for x in supported]),"unsupported_top_score_distribution":distribution([x["scores"][0] if x["scores"] else 0 for x in unsupported])}
 OUT.write_text(json.dumps({"threshold":.10,"case_count":len(rows),"metrics":metrics,"cases":rows},indent=2)+"\n")
 print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()
