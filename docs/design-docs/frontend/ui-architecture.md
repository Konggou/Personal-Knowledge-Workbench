# Frontend UI Architecture

Last Updated: 2026-04-02 16:40 Asia/Shanghai
Related IDs: F-1, F-2, F-3, F-4, F-5, F-6, FLOW-1, FLOW-2, FLOW-3, FLOW-4, FLOW-5, FLOW-6, FLOW-7, FLOW-8

## Frontend Structure

- App shell:
  - global header
  - route-aware navigation
  - page content container
- Main pages:
  - workspace
  - sessions
  - knowledge
  - settings
  - project chat

## Route Responsibilities

- `/workspace`
  - create project
  - list/search projects
  - delete/archive-adjacent project action entrypoint
- `/sessions`
  - grouped session archive across projects
- `/knowledge`
  - grouped source inventory across projects
  - source preview and maintenance
- `/settings`
  - model/runtime configuration
- `/projects/[projectId]`
  - active project work surface
  - sidebar + chat + composer + preview overlay

## Project Page Composition

- `ProjectChatClient` owns project-page orchestration state
- `ProjectChatSidebar` owns project/session navigation actions
- `ProjectChatMessageList` and `ProjectChatMessageCard` render session timeline state
- `ProjectChatComposer` owns turn-level controls for:
  - message input
  - add source
  - deep research
  - web supplementation
  - report generation
- `ProjectSourcePreviewSheet` renders source preview overlays

## UI State Patterns

- React local state is used for view-scoped interaction state
- Network-backed refreshes use API client helpers in `apps/web/src/lib/api.ts`
- The project page keeps per-session composer mode memory for deep research and web supplementation
- Streaming responses append temporary messages first, then reconcile with the final session state

## Interaction Rules

- The message list and composer share the same horizontal axis
- Source bubbles represent only the final evidence set for a message
- Summary and report cards remain inside the session timeline
- Sessions can be renamed or deleted from available session actions
- The V7 refresh flattens project sidebar density:
  - project row shows only source count
  - current project is the only expanded project in the project page sidebar
  - session actions live in an overflow menu

## Testing Surface

- Component-level tests exist for:
  - project chat client
  - app shell
  - workspace page
  - settings page
- Playwright exists for browser-level flows, but current regression confidence is strongest in targeted component tests

## Near-Term Frontend Work

- Complete browser-level verification of the V7 light theme and sidebar interaction changes
- Keep the project page as the primary design target and avoid reintroducing dashboard-like parallel panels
