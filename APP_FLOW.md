# Personal Knowledge Workbench v1 - App Flow

## 1. Purpose

This document defines the chat-first v1 user flow.

Public routes:

- `/workspace`
- `/sessions`
- `/knowledge`
- `/projects/[projectId]`
- `/projects/[projectId]?sessionId=...`

Removed routes:

- `/tasks`
- `/search`
- `/assets`
- dedicated task-detail pages

## 2. Screen List

### 2.1 `/workspace`

Purpose:

- create a new project
- reopen a recent project
- search projects by name

What the user sees:

- a create-project block
- a recent-project list

### 2.2 `/sessions`

Purpose:

- browse recent sessions across all projects

What the user sees:

- sessions grouped by project
- open, rename, and delete actions

### 2.3 `/knowledge`

Purpose:

- manage sources across projects
- search sources
- preview a source before entering chat

What the user sees:

- search input
- project filter
- source groups by project
- a preview panel

### 2.4 `/projects/[projectId]`

Purpose:

- main project chat screen

What the user sees:

- a light top navigation
- a left project-tree sidebar
- a dominant center chat area
- no permanent right knowledge column

### 2.5 `/projects/[projectId]?sessionId=...`

Purpose:

- open one specific session inside the project chat screen

## 3. Primary Navigation Rules

- `Workspace` is the only project entry page.
- `Sessions` is a global browsing page, not the main work surface.
- `Knowledge` owns source search and source management.
- Active work always happens inside `/projects/[projectId]`.
- A project page without `sessionId` must not auto-open an existing session.

## 4. Flow 1 - First Open

Trigger:

- the user opens the app

Sequence:

1. `/` redirects to `/workspace`
2. the user sees the create-project block
3. if no projects exist, the project list is empty

Success result:

- the user understands that work starts by creating or opening a project

Error result:

- if project loading fails, keep the create-project path visible and show retry guidance

## 5. Flow 2 - Create Project

Trigger:

- user submits the create-project form on `/workspace`

Sequence:

1. user enters project name
2. user enters one-line description
3. user submits
4. the system creates the project
5. the app navigates to `/projects/[projectId]`
6. the project opens in empty-state mode

Success result:

- the user lands on the project page with no session selected

Error result:

- inline validation error if the name or description is blank
- keep entered values on failure

## 6. Flow 3 - Project Empty State

Trigger:

- the user enters `/projects/[projectId]` with no `sessionId`

Sequence:

1. the left sidebar loads all projects as a tree
2. the current project is expanded by default
3. the center area does not auto-open any session
4. the center area shows a project empty state
5. the empty state shows:
   - `New Session`
   - `Go to Knowledge`

Success result:

- the user clearly chooses whether to start a conversation or manage knowledge first

Error result:

- if the project does not exist, show not-found

## 7. Flow 4 - Create Session

Trigger:

- user clicks `New Session`

Sequence:

1. the system creates a session under the current project
2. the app navigates to `/projects/[projectId]?sessionId=...`
3. the chat composer becomes visible
4. if the project has no indexed sources, weak-source mode is shown

Success result:

- the user can start chatting immediately

Error result:

- if session creation fails, stay on the project page and show retry guidance

## 8. Flow 5 - Add Source Inside Chat

Trigger:

- user clicks `Add Source` in the composer area

Sequence:

1. a tiny menu opens
2. the menu offers:
   - `Add File`
   - `Add Web Link`
3. if the user selects file upload, a file picker opens
4. if the user selects web link, a small inline URL form opens above the composer
5. after a successful import:
   - the current project source list is updated
   - a lightweight `source update` system card is inserted into the same session

Success result:

- the source becomes available to retrieval without leaving the chat thread

Error result:

- unsupported file type shows validation error
- ingestion failure is surfaced to the user

## 9. Flow 6 - Ask in the Same Session

Trigger:

- user sends a normal chat message

Sequence:

1. the system appends the user message
2. if this is the first user message, the session title is auto-generated
3. the system runs retrieval against the current project knowledge
4. if evidence is found, the system builds a grounded answer from a small final evidence set instead of pasting raw retrieval text
5. the assistant shell appears immediately and the answer streams into the same message
6. when the answer completes, the footer mounts the final source bubble
7. if no evidence is found, source mode falls back to `weak_source_mode` and the chat still streams normally

Success result:

- the answer appears in the same conversation
- the session title becomes meaningful after the first user message

Error result:

- if answering fails, keep the user message visible and show an assistant-side failure state

## 10. Flow 7 - Ask Upgrades to Deep Research

Trigger:

- user toggles `Deep Research` before sending

Sequence:

1. the user stays in the same session
2. the system inserts lightweight status cards, such as:
   - `Researching`
   - `Research complete`
3. retrieval uses a deeper evidence-selection path for this turn
4. the final answer is still streamed into the same message flow

Success result:

- the session feels continuous even when the work becomes more complex

Error result:

- if research fails, the conversation still stays in the same session and shows a recoverable failure message

## 11. Flow 8 - View Sources

Trigger:

- user clicks the source bubble under an assistant answer

Sequence:

1. the message expands a lightweight source-title list
2. only titles are shown at first
3. user clicks one title
4. a detailed source preview opens as an overlay panel

Success result:

- the user can inspect evidence without leaving the conversation

Error result:

- if preview loading fails, keep the message context and show a retry action

## 12. Flow 9 - Save Summary and Generate Report

Trigger:

- user clicks `Save as Summary`
- or clicks `Generate Report`

Sequence:

1. the system uses the latest valid conclusion in the current session
2. a summary card or report card is appended to the same session
3. the original answer remains in place

Success result:

- the user gets a reusable result without leaving the chat thread

Error result:

- if no valid conclusion exists, `Generate Report` stays disabled

## 13. Flow 10 - Use the Knowledge Page

Trigger:

- user opens `/knowledge`
- or clicks the project-level knowledge button from the composer area

Sequence:

1. the page loads source groups by project
2. the user can search or filter by project
3. the user previews a source first
4. the user may click `Enter Chat`
5. the system creates a new session under that project
6. the app navigates to `/projects/[projectId]?sessionId=...`

Success result:

- the user can move from source management to conversation without losing project context

Error result:

- if source loading fails, keep filters visible and show retry guidance
