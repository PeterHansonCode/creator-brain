# Build contract (proposal)

## One signature

Evaluate retrieval and citation integrity with labelled evidence. Security remains a small, explicit boundary rather than a second flagship.

## Vertical slice

Local text/transcript -> source metadata -> deterministic chunks -> embeddings/index -> advisor-filtered retrieval -> structured LLM answer -> citation validation -> visible source excerpts.

Support Hormozi, Naval and Kallaway collections. Start with a few usable documents per advisor, not a bulk scraper. Single-advisor mode and a minimal all-advisor comparison share retrieval/answer code. Comparison reports supported differences or insufficient evidence; never forces disagreement or impersonates the people.

## Contracts

- Source: source_id, advisor_id, title, URL when available, text, attribution/permission note, optional timestamps.
- Chunk: stable chunk_id, source_id, advisor_id, text, offsets/timestamps. Re-ingestion must not silently duplicate the corpus.
- Query: text and selected advisor IDs from a fixed allowed set.
- Answer: status (answered/insufficient_evidence), claims with citation IDs, and per-advisor findings. The server resolves links from its source register, not model-invented URLs.
- Reject citations absent from the actual retrieved set; a valid source ID alone does not prove semantic support for a claim.
- Empty or weak retrieval produces abstention. Real model failures are visible; never substitute fixtures silently.
- Retrieved content is untrusted data. The answer model receives no shell, filesystem-write or external-action tools. Prompt instructions and citation checks reduce risk, but do not prove immunity to prompt injection.

## Evaluation

Start with a small labelled question set, including paraphrases, wrong-advisor cases and unanswerable questions. Label expected sources before tuning. Hold out several questions for final reporting.

Offline metrics: source recall@3, reciprocal rank, advisor isolation, and citation-ID validity. Citation validity and lexical similarity are not factual faithfulness. Separate schema/citation fixtures from live generated-answer assessment.

Run retrieval over the real corpus/index in the gate rather than scoring canned expected outputs alone. Report sample count and configuration. Store an accepted baseline with corpus/version metadata; do not overwrite it automatically during CI. Initially use an explicit allowable absolute drop (proposed 0.05) and show both baseline and new score. Missing baseline/corpus and zero cases fail clearly.

Demonstrate the gate rejects an intentionally degraded retriever. Required GitHub checks are a separate repository setting before describing merge blocking.

## Tests and evidence

Namespace isolation; stable chunking; missing citation rejection; unanswerable question; repeat ingestion; real retrieval quality; deliberate regression failure. Also manually inspect several live generated claims against excerpts and record shortcomings.

## Cuts

No obligatory RAGAS dependency, paid LLM judge, CrewAI/AutoGen, MCP wrapper, AWS deployment, Grafana, PDF ingestion or full YouTube crawler. Add any only after the core and evidence are complete. Local exported transcripts are the initial ingestion format.

## Content

Never publish Peter's private vault. Commit a source register (title, URL, attribution note per source) alongside the ingested material. Never present synthetic example material as a creator quotation. Actual creator sources have since been ingested (see README) -- real public YouTube captions and nav.al transcripts are committed to this repo; whether that's the right redistribution scope for a public release is a separate decision from whether the code works, and hasn't been made yet.
