# Backend Data Model and API Contracts

Last Updated: 2026-04-02 16:40 Asia/Shanghai
Related IDs: F-1, F-2, F-3, F-4, F-5, F-6, F-7, FLOW-2, FLOW-3, FLOW-4, FLOW-5, FLOW-6, FLOW-7, FLOW-8

## Core Data Model

### Application Metadata

- `_app_metadata`
  - key/value store for persisted application configuration such as model settings

### Projects

- `projects`
  - project identity and description
  - external evidence policy
  - lifecycle state (`active`, `archived`)
  - activity timestamps

### Snapshots and Sources

- `project_snapshots`
  - per-project retrieval/index snapshots
- `sources`
  - source metadata for PDFs, DOCX files, and web pages
  - ingestion state, quality level, refresh policy, archive/delete state
- `source_chunks`
  - normalized retrieval chunks linked to snapshots and Qdrant point IDs
- `source_chunk_fts`
  - SQLite FTS5 table for lexical retrieval

### Sessions and Messages

- `sessions`
  - session metadata, title state, soft-delete state
- `session_messages`
  - user prompts
  - assistant answers
  - status cards
  - summary cards
  - report cards
  - source update cards
- `message_sources`
  - final evidence set attached to a message
  - supports project source evidence and external web evidence

### Memory

- `memory_entries`
  - scoped to session or project
  - stores topic/fact pairs with salience and source-message linkage

## Public API Families

### Projects

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/sessions`

### Sessions

- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/projects/{project_id}/sessions`
- `POST /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages/stream`

### Knowledge and Sources

- knowledge-family routes provide grouped source inventory and source creation surfaces
- source-family routes provide preview and source maintenance operations
- source actions include preview, refresh, archive, restore, delete, and web source updates

### Settings

- `GET /api/v1/settings/models`
- `PUT /api/v1/settings/models`

### Admin and Health

- `GET /api/v1/health`
- cleanup routes under `/api/v1/admin`

## Contract Notes

- Session responses expose titles, message counts, latest-message timestamps, and nested messages when full detail is requested
- Chat messages expose:
  - role
  - message type
  - markdown content
  - source mode
  - evidence status
  - disclosure note
  - summary/report support flags
  - nested source evidence
- Source preview responses expose preview chunks with structural context such as headings, field labels, table origin, and excerpt text

## Retrieval Contract Notes

- Project-grounded answers can report `grounded`, `insufficient`, or `conflicting` evidence status
- Message evidence currently models the final evidence set, not internal retrieval candidates
- Source mode distinguishes normal grounded answers from weak-source-mode behavior
