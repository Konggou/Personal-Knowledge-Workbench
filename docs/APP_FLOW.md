# Application Flow

Last Updated: 2026-04-02 16:40 Asia/Shanghai

## Route Inventory

- `/workspace`
- `/sessions`
- `/knowledge`
- `/settings`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=<id>`

## FLOW-1 Open the App and Enter a Project

Entry points:
- User opens the web app root and is redirected into the workspace flow
- User returns later and starts from `/workspace`

Steps:
1. The user lands on the workspace page.
2. The page shows project creation controls and recent active projects.
3. The user either creates a new project or opens an existing one.
4. The system routes to `/projects/[projectId]`.

Success outcome:
- The user reaches the chosen project page.

Failure outcome:
- Project list or project creation errors remain inline on the workspace page.

## FLOW-2 Create a Project and Start the First Session

Entry point:
- Workspace project creation card

Steps:
1. The user enters a project name and description.
2. The system creates the project.
3. The system routes to the project page with no selected session.
4. The project page shows an empty project state.
5. The user creates a new session.
6. The system routes to `/projects/[projectId]?sessionId=<id>`.

Success outcome:
- The user is inside a live session in the new project.

Failure outcome:
- Validation or creation failure keeps the user on the workspace page with an error.

## FLOW-3 Add Sources to a Project

Entry points:
- Project page composer "Add source"
- Knowledge page controls

Steps:
1. The user chooses file upload or web URL ingestion.
2. The system creates source records and starts ingestion.
3. The project source count updates after refresh.
4. The user can inspect sources on the knowledge page or from source previews in chat.

Success outcome:
- The project has retrievable source material.

Failure outcome:
- Unsupported files or ingestion failures show inline feedback.

## FLOW-4 Ask a Grounded Question

Entry point:
- Active project session page

Steps:
1. The user types a message in the composer.
2. The user optionally enables deep research or web supplementation.
3. The system appends the user message and starts assistant streaming.
4. The system streams answer deltas and optional status cards.
5. The final assistant answer appears with final evidence metadata.
6. The user opens the evidence bubble and optionally opens a source preview.

Success outcome:
- The session contains a grounded answer and inspectable sources.

Failure outcome:
- The assistant message shell remains in the session with failure text instead of disappearing.

## FLOW-5 Continue, Rename, or Delete a Session

Entry points:
- Project sidebar
- Sessions page

Steps:
1. The user selects another session from the current project or the global session archive page.
2. The system loads that session into the project page.
3. The user can rename or delete the session from the available actions.
4. If the selected session is deleted from the project page, the page returns to the project state without a selected session.

Success outcome:
- Session state, list state, and current project view remain synchronized.

Failure outcome:
- Errors leave the current session list visible and do not silently remove data.

## FLOW-6 Save a Summary or Generate a Report

Entry point:
- Latest actionable assistant answer inside a session

Steps:
1. The user reaches an assistant answer that supports summary/report actions.
2. The user saves a summary or generates a report.
3. The backend writes a new result card into the same session timeline.
4. The result stays in the conversation rather than opening a separate page.

Success outcome:
- The conversation contains a summary card or report card tied to the latest actionable answer.

Failure outcome:
- If there is no valid actionable answer, report generation remains unavailable or fails with explicit feedback.

## FLOW-7 Manage Knowledge Inventory

Entry point:
- `/knowledge`

Steps:
1. The user filters by project, archived state, or text query.
2. The user previews a source.
3. The user refreshes, archives, restores, edits, or deletes a source.
4. The user can start a new project session from a source context when applicable.

Success outcome:
- Source inventory stays manageable without leaving the app shell.

Failure outcome:
- Busy actions stay scoped to the chosen source and surface visible errors.

## FLOW-8 Manage Model Settings

Entry point:
- `/settings`

Steps:
1. The user opens the settings page.
2. The user edits LLM, embedding, and reranker values.
3. The user saves settings.
4. The UI reflects saved state and masked key status.

Success outcome:
- Runtime model settings are updated through the settings API.

Failure outcome:
- The page keeps form values visible and shows explicit save errors.

## UX State and Edge Cases

- Project pages may load without a selected session and must show a project-level empty state.
- Sessions remember composer toggles such as deep research and web supplementation per session.
- Source previews are overlay interactions, not route transitions.
- Archived projects and deleted sessions should not appear in normal active navigation flows.
- The V7 near-term UI direction changes the visual system, but not the route inventory or flow structure.
