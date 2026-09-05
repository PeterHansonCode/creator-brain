import argparse
import json
from pathlib import Path

from .core import ROOT, Embeddings, Retriever, load_sources


def evaluate(retriever, cases, degraded=False):
    if not cases:
        raise ValueError("Evaluation must contain cases.")
    rows = []
    for case in cases:
        results = [] if degraded else retriever.search(case["query"], case["advisor"])
        ids = list(dict.fromkeys(r["source_id"] for r in results))
        expected = set(case["expected"])
        if not expected:
            raise ValueError("Retrieval cases need gold sources; abstention is tested separately.")
        recall = len(expected.intersection(ids[:3])) / len(expected)
        rr = next((1 / (i + 1) for i, sid in enumerate(ids) if sid in expected), 0)
        rows.append({"id":case["id"], "recall_at_3":recall, "reciprocal_rank":rr,
                     "isolated":all(r["advisor_id"] == case["advisor"] for r in results)})
    return {"cases":len(rows), "recall_at_3":sum(r["recall_at_3"] for r in rows)/len(rows),
            "mrr":sum(r["reciprocal_rank"] for r in rows)/len(rows),
            "advisor_isolation":all(r["isolated"] for r in rows), "details":rows}


def gate(current, baseline, tolerance=0.05):
    if current["cases"] != baseline["cases"] or current["cases"] <= 0:
        return False
    return current["advisor_isolation"] and all(current[k] >= baseline[k] - tolerance for k in ("recall_at_3", "mrr"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true',help='Generate frozen embeddings and explicitly accept an initial baseline.')
    parser.add_argument('--degraded',action='store_true',help='Return no evidence to demonstrate gate failure.')
    args=parser.parse_args()
    cases=json.loads((ROOT/'eval/questions.json').read_text())
    embeddings=Embeddings(offline=not args.prepare)
    retriever=Retriever(load_sources(),embeddings)
    report=evaluate(retriever,cases,args.degraded)
    report['corpus_sha256']=retriever.fingerprint
    baseline_path=ROOT/'eval/baseline.json'
    if args.prepare:
        if baseline_path.exists():
            raise ValueError('Baseline already exists. Review changes explicitly; automatic replacement is refused.')
        embeddings.save_public_cache()
        baseline_path.write_text(json.dumps(report,indent=2))
    baseline=json.loads(baseline_path.read_text())
    passed=report['corpus_sha256']==baseline['corpus_sha256'] and gate(report,baseline)
    print(json.dumps({'passed':passed,**report},indent=2))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
