# Backend Service Architecture

Last Updated: 2026-04-02 16:40 Asia/Shanghai
Related IDs: F-1, F-2, F-3, F-4, F-5, F-6, F-7, FLOW-2, FLOW-3, FLOW-4, FLOW-5, FLOW-6, FLOW-7, FLOW-8

## API Entry Layer

- FastAPI app entry: `apps/api/app/main.py`
- Router composition: `apps/api/app/api/router.py`
- Route families:
  - health
  - projects
  - sessions
  - knowledge
  - sources
  - settings
  - admin cleanup

## Core Service Layers

- `ProjectService`
  - project lifecycle
  - project listing
  - project detail and project-scoped summary data
- `SessionService`
  - session lifecycle
  - session retrieval
  - session rename/delete
- `SessionTurnService`
  - shared turn orchestration across synchronous and streaming message flows
- `GroundedGenerationService`
  - grounded answer construction
  - evidence-aware generation behavior
- `SearchService`
  - retrieval pipeline coordination
- `RerankerService`
  - reranking backend selection and execution
- `KnowledgeService` / `SourceService`
  - source ingestion, maintenance, preview, archive/restore/delete
- `MemoryService`
  - session memory and project memory management
- `SettingsService`
  - persisted model/runtime configuration
- `CleanupService`
  - background deletion and retention cleanup

## Storage Boundaries

- SQLite is the entity/state system of record
- Qdrant stores vector search points derived from source chunks
- Search repository code maintains retrieval index state and FTS synchronization

## Retrieval and Generation Flow

1. The session route receives a user turn.
2. Session services create/update session message state.
3. Search services retrieve project evidence through lexical + semantic search with fusion and optional reranking.
4. Grounded generation services compose the final answer and evidence payload.
5. Session services write final assistant messages and message-source links.
6. Streaming routes emit deltas, status cards, and final messages to the frontend.

## Background and Startup Behavior

- Database initialization runs at API startup
- Retrieval index verification runs at startup
- Qdrant collection verification runs at startup
- Cleanup tasks run in the background after startup and do not block API readiness

## Confirmed Near-Term Backend Context

- The product direction stays unchanged during the V7 visual refresh
- Backend work remains focused on the existing project/session/source/retrieval model
- The current branch still contains unrelated backend modifications outside the spec refresh and they should not be conflated with the documentation migration
