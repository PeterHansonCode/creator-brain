# Creator Brain

Planning skeleton — implementation has not started.

A proposed knowledge assistant over three curated advisor source collections, with source-linked answers and attributed comparisons. Signature strength: retrieval and citation evaluation.

See [the build contract](docs/BUILD-CONTRACT.md). Proposed stack: Python, FastAPI, local embeddings/Chroma, a verified available LLM, and GitHub Actions. The exact provider remains undecided.

## Planned layout

```text
src/creator_brain/ ingestion, retrieval, answer schemas and API
data/sample/       original or redistribution-approved demo sources
eval/              labelled questions, accepted baseline and gate
tests/             source isolation, citation and gate tests
web/               query, sources and comparison view
docs/              source register, decisions and demo evidence
```

Setup, test commands, screenshots and measured results will be added when implemented. No RAGAS, MCP, production deployment or measured accuracy is claimed.
