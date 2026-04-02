# Agent Operating Guide

## Start Here
1. Read `progress.txt`.
2. Open the active execution plan referenced there.
3. Read `docs/DESIGN.md` for the design index.
4. Open only the detailed docs needed for the task.

## Source Of Truth
- Current implementation truth: repository code and tests.
- Product and target-state truth: `docs/PRD.md` and `docs/APP_FLOW.md`.
- Technical and architecture truth: `docs/TECH_STACK.md` and files under `docs/design-docs/`.
- Active execution truth for the current thread: the file in `docs/exec-plans/active/` referenced by `progress.txt`.

When docs conflict:
1. Latest explicit user instruction
2. Repository code for current behavior
3. `docs/PRD.md`
4. `docs/APP_FLOW.md`
5. `docs/TECH_STACK.md`
6. `docs/DESIGN.md` and linked detailed design docs
7. `progress.txt`

## Product Boundaries
- Product identity: a local-first, chat-first personal knowledge workbench.
- Primary mental model: project -> session -> message -> sources.
- Keep the core loop intact: create project, create session, add sources, ask inside a project, inspect sources.
- Do not revert to a task-first product.
- Do not reintroduce `/tasks`, `/search`, or `/assets` as front-stage product surfaces.
- Do not add multi-user collaboration, authentication, or workspace-centric scope unless explicitly requested.

## Public Surface
- Routes: `/workspace`, `/sessions`, `/knowledge`, `/settings`, `/projects/[projectId]`
- API families: `/api/v1/projects`, `/api/v1/sessions`, `/api/v1/knowledge`, `/api/v1/sources`, `/api/v1/settings`

## Data And Backend Constraints
- SQLite is the only structured state store.
- Qdrant is the default vector retrieval backend.
- Soft delete semantics apply to user-facing deletion flows.
- Local schema rebuilds are allowed; backward-compatible migrations are not required by default.

## Frontend Constraints
- Project page stays: light top navigation, left sidebar / rail, centered chat column, bottom composer on the same axis.
- No persistent right-side knowledge panel.
- Summary cards and report cards remain inside the session timeline.
- Sources open from lightweight evidence chips into an overlay-style detailed preview.

## Documentation Map
- Product requirements: `docs/PRD.md`
- App flow: `docs/APP_FLOW.md`
- Technical baseline: `docs/TECH_STACK.md`
- Design index: `docs/DESIGN.md`
- Frontend detail: `docs/design-docs/frontend/`
- Backend detail: `docs/design-docs/backend/`
- Active plans: `docs/exec-plans/active/`
- Completed plans: `docs/exec-plans/completed/`

## Execution Memory Rules
- `progress.txt` is mandatory and must stay current.
- Store step-by-step plans in `docs/exec-plans/active/`.
- Move finished plans into `docs/exec-plans/completed/`.
- Keep `AGENTS.md` short; put durable detail in `docs/`.

## Verification Expectations
- Before claiming completion, run the narrowest meaningful verification for the files changed.
- Record any remaining gaps or flaky commands in the active execution plan and in the final response.
