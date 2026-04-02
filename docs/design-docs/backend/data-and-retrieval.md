# Backend Design: Data and Retrieval

Last Updated: 2026-04-02 16:40 CST

Related IDs: `F-3`, `F-4`, `F-5`, `F-7`, `FLOW-4`, `FLOW-5`, `FLOW-6`, `FLOW-7`, `FLOW-9`

## Persistence Model

Structured state lives in SQLite. The current schema centers on these tables:

- `_app_metadata`
- `projects`
- `project_snapshots`
- `sources`
- `source_chunks`
- `source_chunk_fts`
- `sessions`
- `session_messages`
- `message_sources`
- `memory_entries`

## Table Roles

- `projects`
  - top-level knowledge containers
- `project_snapshots`
  - track searchable source snapshot versions per project
- `sources`
  - material registry for PDF, DOCX, and web page sources
- `source_chunks`
  - normalized retrieval chunks, keyed to snapshots and Qdrant point IDs
- `source_chunk_fts`
  - lexical retrieval index over title and normalized chunk text
- `sessions`
  - project-scoped conversation threads
- `session_messages`
  - user prompts, assistant answers, status cards, summary cards, report cards, and source updates
- `message_sources`
  - final evidence attachments per assistant message
- `memory_entries`
  - extracted facts at session or project scope

## Retrieval Pipeline

- lexical retrieval via SQLite FTS5 and BM25
- semantic retrieval via Qdrant
- rank fusion via RRF
- reranking via:
  - `rule`
  - `cross_encoder_local`
  - `cross_encoder_remote`

Current baseline defaults:

- `retrieval_mode=hybrid`
- `lexical_candidate_limit=8`
- `semantic_candidate_limit=8`
- `rrf_k=30`
- `reranker_top_n=4`
- `hyde_policy=off`
- `final_retrieval_limit=3`

## Grounded Answer Contract

- Assistant answers may be:
  - project grounded
  - weak-source mode
- Final evidence only is attached to the answer record.
- Evidence metadata carries source title, type, URI, location label, excerpt, and relevance score.
- Web supplementation can appear as external evidence and later be saved into project knowledge.

## Settings Contract

- Global model configuration is stored in `_app_metadata`.
- SQLite-stored settings override environment defaults at runtime.
- API keys are masked in the frontend contract after persistence.

## Data and Product Constraints

- SQLite is the only structured source of truth.
- Qdrant is the default vector backend.
- Local schema rebuilds are allowed; backward-compatible migration support is not the primary design constraint.
- Public frontend flows must not depend on deprecated task APIs even if stale compiled artifacts still exist in the repo.
