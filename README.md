# Creator Brain

A local knowledge assistant over three advisor source collections. Ask one advisor or compare attributed findings across Alex Hormozi, Naval Ravikant and Kallaway. Generated claims must cite retrieved chunks; links come from the source register.

**Signature:** reproducible retrieval evaluation that fails when ranking quality regresses. Local models avoid paid API dependencies.

## Run

Install Python 3.12 and Ollama:

```sh
ollama pull all-minilm
ollama pull qwen3:4b-instruct
python -m venv .venv
# Activate .venv using your platform's standard activation command.
pip install -r requirements.txt
python -m uvicorn brain.api:app --host 127.0.0.1 --port 3200
```

Open http://127.0.0.1:3200. Ollama must be running on port 11434 for new query embeddings and generation. "Show sources only" skips generation. No fixtures replace failed live answers.

```text
Attributed source JSON -> stable chunks -> MiniLM embeddings -> Chroma
Question -> embedding -> advisor filter -> ranked excerpts
  -> Qwen3 structured claims -> citation validation -> linked answers
```

Council mode shows each advisor's grounded findings plus a deterministic synthesis: a lexical-overlap heuristic over the advisors' own already-cited claims surfaces shared themes ("agreement") versus claims with no shared vocabulary ("distinct perspectives"). This is a structural comparison, not a semantic judgement and not a new model call — it can never invent a claim beyond what an advisor's individual answer already cited, and it stays fully offline-testable. Chroma indexes the small corpus in memory using stable IDs. No public hosting or MCP wrapper is included.

## Evaluate without a running model

```sh
python -m pytest -q
python -m brain.evaluate
python -m brain.evaluate --degraded
```

The final command must exit 1: it deliberately removes all retrieval results. CI never overwrites the baseline. An absolute drop greater than 0.05 in MRR or recall@3, changed corpus, changed case count, or advisor leakage fails the gate.

The committed cache contains real MiniLM vectors for public sample texts and labelled questions. Offline evaluation executes Chroma retrieval, not scoring canned answers. It measures the frozen embedding configuration, not arbitrary model updates. Interactive query vectors are not written to the committed cache.

Local results on the real ingested corpus (70 sources / 3,159 chunks across Hormozi, Naval, and Kallaway): **MRR 0.593, recall@3 0.778** across 9 hand-labelled questions (2 dev + 1 holdout per advisor), no cross-advisor leakage; degraded retrieval still fails the gate as expected. Two questions miss the top 3 entirely, both broadly-phrased queries against advisors whose own back catalog is thematically repetitive (e.g. Kallaway has six separate videos about hooks and viewer psychology), so several genuinely relevant chunks compete for the same slots. This is an honest, imperfect baseline from real embeddings and real transcripts, not a curated result, and it's what the CI gate now protects against regressing.

Seven contract tests cover chunk stability, foreign citations, abstention, regression rejection, API boundaries, and council synthesis (agreement/distinct-perspective detection, plus a check that synthesis citations always trace back to an advisor's own cited evidence). A real Naval answer was generated and checked against its excerpts (around 12 seconds in the observed run). All-advisor live testing and user acceptance remain. GitHub Actions is configured but remote execution is not verified. Required repository checks must be configured separately to block merging.

## Sources and limits

The corpus (data/sample/sources.json) is real content: 70 sources / 3,159 chunks pulled from public YouTube captions for Hormozi and Kallaway (scripts/ingest_youtube.py) and from Naval's own site transcripts (scripts/ingest_nav_al.py -- his podcast episodes are co-hosted, so auto-captions have no speaker labels and can't be cleanly attributed to him alone). Both scripts are checked in and re-runnable. Add labelled questions before tuning. Do not commit private vault notes.

Citation-ID validity does not establish factual entailment. The model has no action tools, source text is marked untrusted and invalid IDs are rejected; these controls do not prove prompt-injection immunity. Similarity-based abstention is a heuristic. The UI reports failures instead of inventing fallback answers.

See [build contract](docs/BUILD-CONTRACT.md). The RAGAS package is not used.
