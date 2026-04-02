# Design

Last Updated: 2026-04-02 16:40 Asia/Shanghai

## System Summary

The system is a local-first web application with a Next.js frontend and a FastAPI backend. The frontend exposes a chat-first research workspace around projects and sessions. The backend owns structured state, source ingestion, retrieval, generation, memory, and model configuration. SQLite stores application entities and retrieval metadata, while Qdrant stores vector points for semantic search.

## Frontend Boundaries

- The frontend owns routing, page composition, optimistic session interactions, streaming UI updates, source previews, and settings forms.
- The frontend does not implement retrieval, generation, ingestion, or persistence logic locally.
- The project page is the primary working surface and combines:
  - project sidebar
  - active chat stage
  - source preview overlay
  - aligned composer controls
- The V7 near-term direction updates presentation density and visual hierarchy without changing the route model.

## Backend Boundaries

- The backend owns:
  - project lifecycle
  - session lifecycle
  - source ingestion and maintenance
  - retrieval and reranking
  - grounded answer generation
  - summary/report card creation
  - model settings persistence
  - cleanup jobs
- The backend does not render UI state and does not expose deprecated public task-first surfaces.

## Shared Contracts

- The frontend and backend share project/session/source/message contracts defined through the REST API.
- Session message streaming is exposed as a server event stream for incremental answer rendering.
- Source previews and message evidence bubbles share source IDs so preview overlays can resolve the correct source details.
- Settings contracts cover LLM, embedding, and reranker configuration.

## Design Doc Index

### Frontend

- docs/design-docs/frontend/ui-architecture.md
- docs/design-docs/frontend/visual-system.md

### Backend

- docs/design-docs/backend/service-architecture.md
- docs/design-docs/backend/data-model-and-api.md
