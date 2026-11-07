# Implementation roadmap

## Built — Phases 0 and 1: usable local product

- Typed component and selection models.
- Versioned catalogue with educational metadata and implementation status.
- Compatibility checks and deterministic repository renderer.
- Basic CLI, tests, sample selection, and generated-project contract.
- Visual configurator, validation and generation HTTP APIs.
- SQLite-backed saved configurations.
- Module and complete-repository ZIP downloads.
- Browser, API, archive, security-boundary, and generated-project tests.

## Next — provider-complete client release

- Reviewed templates for TXT/PDF parsing, fixed chunking, OpenAI embeddings, pgvector,
  FastAPI ingestion/query routes, citations, tenant filters, migrations, and integration tests.
- Isolated document-processing worker and upload limits.

## Proposed — Phase 2: production hybrid RAG

- CSV/XLSX/DOCX/PPTX adapters, OCR, Redis/ARQ ingestion, PostgreSQL full-text search,
  weighted RRF, reranking, metadata filters, observability, feedback, and evaluation gates.
- Provider compatibility matrices, dimension-aware migrations, cost/latency estimates,
  saved configurations, and upgrade reports.

## Proposed — Phase 3: delivery and bounded agentic retrieval

- Cloud deployment adapters, secret-manager/IAM generation, team workspaces, hosted APIs,
  industry templates, component marketplace, and signed/versioned components.
- Optional bounded retrieval agents only for tasks requiring multi-step source selection or
  query decomposition, with budgets, tool allowlists, traces, and deterministic fallback.
