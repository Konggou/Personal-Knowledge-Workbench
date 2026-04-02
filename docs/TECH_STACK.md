# Technical Stack

Last Updated: 2026-04-02 16:40 Asia/Shanghai

## Monorepo and Package Management

- Root package manager: `pnpm@10.32.1`
- Workspace manifest: `pnpm-workspace.yaml`
- Root package name: `agentic-rag-workbench`

## Frontend Runtime

- Framework: `Next.js 16.1.6`
- UI runtime: `React 19.2.4`
- Language: `TypeScript 5.9.3`
- State/data libraries:
  - `@tanstack/react-query 5.90.21`
  - `zustand 5.0.11`
- UI support libraries:
  - `@radix-ui/react-dialog 1.1.15`
  - `@radix-ui/react-dropdown-menu 2.1.16`
  - `@radix-ui/react-scroll-area 1.2.10`
  - `@radix-ui/react-slot 1.2.4`
  - `@radix-ui/react-tooltip 1.2.8`
  - `lucide-react 0.577.0`
- Markdown rendering:
  - `react-markdown 10.1.0`
  - `remark-gfm 4.0.1`
- Validation:
  - `zod 4.3.6`

## Frontend Routes

- `/workspace`
- `/sessions`
- `/knowledge`
- `/settings`
- `/projects/[projectId]`

## Frontend Tooling

- Test runner: `Vitest 4.0.18`
- DOM testing: `@testing-library/react 16.3.0`, `@testing-library/jest-dom 6.9.1`, `jsdom 27.1.0`
- E2E runner: `Playwright 1.58.2`
- Type checking: `tsc --noEmit`

## Backend Runtime

- Language: `Python 3.12`
- API framework: `FastAPI 0.135.1`
- ASGI server: `uvicorn 0.41.0`
- Validation and data models:
  - `pydantic 2.12.5`
  - `sqlmodel 0.0.37`
- HTTP client: `httpx 0.28.1`
- Multipart uploads: `python-multipart 0.0.22`

## Retrieval, Generation, and Knowledge Processing

- Orchestration/runtime graph: `langgraph 1.1.2`
- PDF parsing: `pypdf 6.8.0`
- DOCX parsing: `python-docx 1.2.0`
- Vector client: `qdrant-client 1.17.0`
- Embeddings and local models: `sentence-transformers 5.2.3`
- OCR support: `rapidocr-onnxruntime 1.4.4`

## Storage and State

- Structured application state: SQLite
- Schema definition: `apps/api/app/db/schema.sql`
- Vector retrieval backend: Qdrant
- Default state center:
  - projects
  - project snapshots
  - sources
  - source chunks and FTS index
  - sessions
  - session messages
  - message sources
  - memory entries
  - application metadata

## API Surface

- Prefix: `/api/v1`
- Families:
  - `/health`
  - `/projects`
  - `/sessions`
  - `/knowledge`
  - `/sources`
  - `/settings`
  - `/admin`

## Local Runtime Assumptions

- Deployment model: local-first, single-user
- Web default origin: `http://127.0.0.1:3000`
- API default origin in frontend client: `http://127.0.0.1:8000`
- Allowed CORS origins include localhost and loopback hosts for local development

## Verification Commands

- Frontend dev: `corepack pnpm --dir apps/web dev`
- Frontend build: `corepack pnpm --dir apps/web build`
- Frontend typecheck: `corepack pnpm --dir apps/web typecheck`
- Frontend tests: `corepack pnpm --dir apps/web test`
- Frontend E2E: `corepack pnpm --dir apps/web test:e2e`
- API dev: `apps/api/.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8010`
- Backend tests: `apps/api/.venv/Scripts/python.exe -m pytest -q`

## Integration Boundaries

- The frontend consumes only the public `/api/v1/*` families.
- SQLite is the only structured state authority.
- Qdrant is the vector store, not the source of truth for app entities.
- Model configuration is served through the settings API rather than hardcoded UI constants.
