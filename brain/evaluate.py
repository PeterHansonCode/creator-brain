import argparse
import hashlib
import json
from pathlib import Path

from .core import ROOT, Embeddings, Retriever, load_sources


def evaluate(retriever, cases, degraded=False):
    if not cases:
        raise ValueError("Evaluation must contain cases.")
    rows = []
    for case in cases:
        results = [] if degraded else retriever.search(case["query"], case["advisor"])
        # Chunk-level ranking, not deduplicated by source: reciprocal rank
        # and recall@3 both read positions straight off the retriever's own
        # chunk order. A prior version deduplicated ids-by-source before
        # computing reciprocal rank, which silently compresses the true
        # position whenever a non-gold source places more than one chunk
        # ahead of the gold source (e.g. ranks [wrong, wrong-same-source,
        # gold] scored as rank 2, i.e. 0.5, instead of the true rank 3, i.e.
        # 1/3). Using raw chunk order for both metrics avoids that
        # definitional mismatch; it happens not to change this project's
        # current 9-case baseline, but would have on a corpus where a single
        # source's chunks cluster near the top.
        ids = [r["source_id"] for r in results]
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


def questions_fingerprint(cases):
    # The gate previously only checked case COUNT, so swapping in a
    # different set of questions with the same number of cases (e.g. easier
    # ones) would silently pass as "no regression". This hashes the actual
    # question identity (id, query, expected sources, split) so a changed
    # benchmark is detected as a benchmark change, not evaluated as if it
    # were the same one.
    normalized = [{"id": c["id"], "query": c["query"], "advisor": c["advisor"],
                   "split": c.get("split"), "expected": sorted(c["expected"])} for c in cases]
    blob = json.dumps(normalized, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def gate(current, baseline, tolerance=0.05):
    if current["cases"] != baseline["cases"] or current["cases"] <= 0:
        return False
    if "questions_sha256" in baseline and current.get("questions_sha256") != baseline["questions_sha256"]:
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
    report['questions_sha256']=questions_fingerprint(cases)
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
