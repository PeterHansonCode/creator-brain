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

Council mode currently shows separately grounded findings side by side. It does not yet generate a cross-advisor synthesis or assert disagreements. Chroma indexes the small corpus in memory using stable IDs. No public hosting or MCP wrapper is included.

## Evaluate without a running model

```sh
python -m pytest -q
python -m brain.evaluate
python -m brain.evaluate --degraded
```

The final command must exit 1: it deliberately removes all retrieval results. CI never overwrites the baseline. An absolute drop greater than 0.05 in MRR or recall@3, changed corpus, changed case count, or advisor leakage fails the gate.

The committed cache contains real MiniLM vectors for public sample texts and labelled questions. Offline evaluation executes Chroma retrieval, not scoring canned answers. It measures the frozen embedding configuration, not arbitrary model updates. Interactive query vectors are not written to the committed cache.

Initial local results: **MRR 0.889 across 9 questions**, recall@3 1.0, no cross-advisor results; degraded retrieval failed. With only two documents per advisor, recall@3 is trivial and not a useful headline. Three questions labelled holdout were included in this initial final run and are now exposed. This is a tiny development benchmark, not broad accuracy evidence.

Five contract tests cover chunk stability, foreign citations, abstention, regression rejection and API boundaries. A real Naval answer was generated and checked against its excerpts (around 12 seconds in the observed run). All-advisor live testing and user acceptance remain. GitHub Actions is configured but remote execution is not verified. Required repository checks must be configured separately to block merging.

## Sources and limits

The sample JSON contains six short original research paraphrases with primary-source links, not creator transcripts or quotations. Expand it with approved texts for useful depth. Add labelled questions before tuning. Do not commit private vault notes. Ingestion currently accepts JSON text records, not automatic YouTube scraping.

Citation-ID validity does not establish factual entailment. The model has no action tools, source text is marked untrusted and invalid IDs are rejected; these controls do not prove prompt-injection immunity. Similarity-based abstention is a heuristic. The UI reports failures instead of inventing fallback answers.

See [build contract](docs/BUILD-CONTRACT.md). The RAGAS package is not used.
