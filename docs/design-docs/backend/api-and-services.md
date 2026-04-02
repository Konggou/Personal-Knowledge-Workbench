# Backend Design: API and Services

Last Updated: 2026-04-02 16:40 CST

Related IDs: `F-1`, `F-2`, `F-3`, `F-4`, `F-5`, `F-6`, `F-7`, `FLOW-2`, `FLOW-3`, `FLOW-4`, `FLOW-5`, `FLOW-7`, `FLOW-8`, `FLOW-9`

## API Surface

### Health

- `GET /api/v1/health`

### Projects

- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/sessions`

### Sessions and Messaging

- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages/stream`
- `GET /api/v1/sessions/{session_id}/events`
- `POST /api/v1/sessions/{session_id}/summary`
- `POST /api/v1/sessions/{session_id}/report`
- `DELETE /api/v1/messages/{message_id}`

### Knowledge and Sources

- `GET /api/v1/knowledge`
- source routes under `/api/v1/sources` for source preview and source actions

### Settings

- model settings routes under `/api/v1/settings`

### Admin

- cleanup routes under `/api/v1/admin`

## Service Map

- `ProjectService`
  - project CRUD and project-level metadata
- `SessionService`
  - session CRUD, turn entrypoints, summaries, reports, result card deletion
- `SessionTurnService`
  - shared turn orchestration steps used by sync and stream paths
- `KnowledgeService`
  - grouped knowledge listing
- `SourceService`
  - ingestion, preview, refresh, archive/restore/delete, web source edits
- `SettingsService`
  - global model-setting persistence
- `CleanupService`
  - archived-project cleanup flows
- Retrieval and generation services:
  - `SearchService`
  - `EmbeddingService`
  - `RerankerService`
  - `GroundedGenerationService`
  - `WebResearchService`
  - `AgentOrchestratorService`
- `MemoryService`
  - session/project memory extraction and lookup

## Request/Response Principles

- Frontend receives grouped project/session/source payloads instead of assembling these groups client-side.
- Streaming message turns emit deltas, status cards, and final answer completion events.
- Summary and report generation mutate session history by appending result cards.
- Settings routes return masked API-key state instead of secret values.

## Current Behavioral Notes

- Delete semantics are soft-delete oriented for projects, sessions, and sources where appropriate.
- The backend keeps public product language centered on projects, sessions, messages, and sources even though internal orchestration may be agentic.
- Cleanup behavior is intentionally admin-scoped, not a public end-user flow.
