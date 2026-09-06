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

Council mode shows each advisor's grounded findings plus a deterministic synthesis: a lexical-overlap heuristic over the advisors' own already-cited claims groups pairs into "shared topics" (high vocabulary overlap) versus "distinct perspectives" (little overlap). An earlier version tried to call the first group "agreement", with a negation check meant to keep contradicting claims out of it -- that doesn't hold up (a regex can't reliably catch every contraction, and a pure antonym pair like "improves" vs. "harms" has no negation word for any regex to find), so neither bucket now claims agreement or disagreement at all. Both always show the full text of both claims, specifically so you can judge that yourself. This is a structural comparison, not a semantic judgement and not a new model call — it can never invent a claim beyond what an advisor's individual answer already cited, and it stays fully offline-testable. Chroma indexes the small corpus in memory using stable IDs. No public hosting or MCP wrapper is included.

## Evaluate without a running model

```sh
python -m pytest -q
python -m brain.evaluate
python -m brain.evaluate --degraded
```

The final command must exit 1: it deliberately removes all retrieval results. CI never overwrites the baseline. An absolute drop greater than 0.05 in MRR or recall@3, changed corpus, changed case count, or advisor leakage fails the gate.

The committed cache contains real MiniLM vectors for public sample texts and labelled questions. Offline evaluation executes Chroma retrieval, not scoring canned answers. It measures the frozen embedding configuration, not arbitrary model updates. Interactive query vectors are not written to the committed cache.

Local results on the real ingested corpus (70 sources / 3,161 chunks across Hormozi, Naval, and Kallaway): **MRR 0.556, recall@3 0.667** across 9 hand-labelled questions (2 dev + 1 holdout per advisor), no cross-advisor leakage; degraded retrieval still fails the gate as expected. This baseline was regenerated after a code review caught two real bugs: nav.al's speaker-attribution parser was missing an inline-wrapped speaker label and silently folding a co-host's dialogue into Naval's corpus, and YouTube caption cleaning was deduplicating repeated lines anywhere in a video instead of only adjacent rolling-caption repeats. The evaluation script itself was also fixed (reciprocal rank no longer gets computed after a source-deduplication step that could quietly compress the true rank). So this number moving down from an earlier 0.593/0.778 reflects real fixes, not a retrieval regression -- it's a more honest measurement of the same underlying retriever, not a worse one.

Three questions miss the top 3 entirely (h1, k2, k3), all against advisors whose own back catalog is thematically repetitive. For k3 specifically: the gold chunk ranks 4th out of 1,194 Kallaway chunks (cosine 0.697), edged out by two other Kallaway videos that are also substantively about audience growth and social algorithms -- genuine topical overlap within one creator's catalog, not a bug, and the same pattern already seen in h1/k2. This is an honest, imperfect baseline from real embeddings and real transcripts, not a curated result, and it's what the CI gate now protects against regressing.

Twenty tests across two files cover chunk stability, foreign citations, abstention, regression rejection (including a question-set fingerprint so a swapped benchmark of the same size can't silently pass), API boundaries, per-advisor failure isolation, and request-size limiting for both a declared oversized Content-Length and a request that omits it entirely (caught by reading the stream directly and cutting it off, rather than buffering the whole thing first, which is what a review found the original Content-Length-only check still allowed); council synthesis (shared-topics/distinct-perspective grouping, a check that neither bucket claims semantic agreement even for a contraction-negated or pure-antonym claim pair, plus a check that synthesis citations always trace back to an advisor's own cited evidence); the nav.al speaker-attribution parser -- rewritten to walk the real HTML parse tree instead of matching a single anchored regex, so a bolded speaker label is recognized regardless of which way it's nested (both page templates, the inline-wrapped-label case that used to misattribute a co-host's words to Naval in either nesting direction, and a label with a non-breaking space inside the bold run); and the advisor `<select>` markup itself, parsed with the stdlib html.parser rather than trusted by eye -- a hand-authoring slip (`</option value="hormozi">` instead of `</option><option value="hormozi">`) had silently collapsed the dropdown to a single "All three advisors" choice with no way to pick one advisor, caught live during a demo and missed by every prior review since nothing had ever actually parsed the HTML. A real Naval answer was generated and checked against its excerpts (around 12 seconds in the observed run). All-advisor live testing and user acceptance remain. GitHub Actions is configured but remote execution is not verified. Required repository checks must be configured separately to block merging.

## Sources and limits

The corpus (data/sample/sources.json) is real content: 70 sources / 3,161 chunks pulled from public YouTube captions for Hormozi and Kallaway (scripts/ingest_youtube.py) and from Naval's own site transcripts (scripts/ingest_nav_al.py -- his podcast episodes are co-hosted, so auto-captions have no speaker labels and can't be cleanly attributed to him alone). Both scripts are checked in and re-runnable. Add labelled questions before tuning. Do not commit private vault notes.

Citation-ID validity does not establish factual entailment. The model has no action tools, source text is marked untrusted and invalid IDs are rejected; these controls do not prove prompt-injection immunity. Similarity-based abstention is a heuristic. The UI reports failures instead of inventing fallback answers.

See [build contract](docs/BUILD-CONTRACT.md). The RAGAS package is not used.
