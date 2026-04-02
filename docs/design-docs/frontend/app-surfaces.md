# Frontend Design: App Surfaces

Last Updated: 2026-04-02 16:40 CST

Related IDs: `F-1`, `F-2`, `F-3`, `F-7`, `F-8`, `FLOW-1`, `FLOW-2`, `FLOW-3`, `FLOW-4`, `FLOW-9`

## Surface Inventory

### `/workspace`

- Purpose: project creation and project entry
- Primary elements:
  - create-project form
  - recent project list
  - project search
- UI rule:
  - This is an entry page, not the main work area.

### `/sessions`

- Purpose: global grouped session browsing
- Primary elements:
  - project-group sections
  - session rows
  - rename/delete actions
- UI rule:
  - This page supports browsing and maintenance, but does not replace the project page as the main work surface.

### `/knowledge`

- Purpose: grouped knowledge management
- Primary elements:
  - filters
  - grouped source lists
  - source actions
  - source preview drawer
- UI rule:
  - Knowledge remains a management page, not a constant sidebar inside project chat.

### `/settings`

- Purpose: global model configuration
- Primary elements:
  - LLM section
  - embedding section
  - reranker section
- UI rule:
  - It owns system configuration only, not project or knowledge workflows.

### `/projects/[projectId]`

- Purpose: main work area
- Primary elements:
  - light top navigation
  - left project tree sidebar
  - centered chat column
  - centered composer column
  - source preview sheet
- UI rule:
  - No permanent right-side knowledge panel.
  - No large project dashboard header.
  - Summary/report cards stay in the session stream.

## Navigation Rules

- The product mental model is project-first and session-inside-project, not task-first.
- Entering a project without a `sessionId` must not auto-open a recent session.
- The project page must be able to operate in both empty-project state and active-session state.

## Global Design Rules

- Product terms stay limited to: Project, Session, Message, Knowledge, Source, Deep Research, Save as Summary, Generate Report.
- Do not expose `task`, `asset`, or similar legacy frontend terms.
- V7 visual direction:
  - lighter reading-first surfaces
  - lower card density
  - flatter project tree
  - slightly branded but lighter top navigation

## State Management Notes

- Server-loaded route data seeds the initial client state.
- Project chat client owns local sidebar state, selected session refresh, source preview state, and composer toggle memory.
- Query and grouped-list pages remain thin stateful clients over backend data.
