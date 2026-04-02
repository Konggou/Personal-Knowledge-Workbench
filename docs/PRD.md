# Personal Knowledge Workbench PRD

Last Updated: 2026-04-02 16:40 Asia/Shanghai

## Product Summary

Personal Knowledge Workbench is a local-first, single-user research workspace for building project-scoped knowledge bases and asking grounded questions against them. The product centers on a chat workflow inside a project, with explicit evidence, source management, and structured outputs that stay in the conversation.

## Target Users

- Primary: individual knowledge workers managing long-running research topics
- Primary: users collecting PDFs, DOCX files, and web pages into a project before asking questions
- Secondary: technically fluent users who want local execution, explicit sources, and configurable retrieval/generation models

## Problems Solved

- Dispersed files and web notes lack a project-scoped container
- Generic chat tools do not reliably answer from user-owned materials
- Answers without evidence are hard to validate or reuse
- Long-running research threads need memory, summaries, and reports inside the same thread

## Goals

- Provide a stable project -> session -> message workflow for grounded Q&A
- Make source ingestion and source preview part of the main workflow, not a side tool
- Keep final evidence visible and auditable on every substantial answer
- Support deeper research, web supplementation, summaries, and reports without leaving the active session
- Maintain local-first operation with SQLite as the structured state system and Qdrant as the default vector backend

## Success Metrics

- Users can complete the core loop: create project -> create session -> add sources -> ask grounded question -> inspect sources
- Grounded answers include final evidence bubbles for relevant responses
- Sessions can be continued, renamed, deleted, summarized, and turned into reports without leaving the project page
- Settings allow model, embedding, and reranker configuration without manual file edits

## In Scope Features

- F-1 Project workspace and project lifecycle
- F-2 Session management inside projects
- F-3 Grounded chat with evidence bubbles
- F-4 Knowledge ingestion and knowledge management
- F-5 Session-level advanced actions: deep research, web supplementation, summaries, reports
- F-6 Model and retrieval settings
- F-7 Local-first retrieval and memory runtime

## Out of Scope

- Multi-user collaboration
- Authentication and remote workspace concepts
- Public sharing workflows
- Reintroducing task-first UI, `/tasks`, `/search`, or `/assets` as public product surfaces
- Turning the product into a generic agent platform

## Non-Goals

- Cloud-first orchestration
- Enterprise admin features
- Background team workflows
- Separate report pages outside the session timeline

## User Stories

- As a user, I can create a project so a topic has its own knowledge container.
- As a user, I can create and switch sessions inside a project so each discussion thread stays scoped.
- As a user, I can upload a PDF, DOCX, or web page so the project can answer from those materials.
- As a user, I can ask a question in a project session and inspect the final sources behind the answer.
- As a user, I can enable deep research or web supplementation for a specific turn when the question needs it.
- As a user, I can save a useful answer as a summary or generate a report without leaving the conversation.
- As a user, I can manage model settings locally from the settings page.

## Feature Acceptance Criteria

### F-1 Project Workspace and Project Lifecycle

- The app exposes `/workspace` and `/projects/[projectId]` as primary project entry points.
- Users can create a project with a name, description, and external browsing policy.
- Project listing supports search and archived project visibility.
- Project deletion is soft-delete oriented and archived projects are excluded from normal active lists.

### F-2 Session Management

- Users can create a new session inside a project.
- The project page can load with or without a selected `sessionId`.
- Sessions can be renamed and deleted.
- Session titles can be generated automatically after early conversation turns and overridden manually.

### F-3 Grounded Chat with Evidence

- User prompts and assistant answers appear in the session timeline.
- Streaming chat is supported through the session message stream endpoint.
- Assistant answers can carry source bubbles representing the final evidence set.
- Source previews open detailed project source content without navigating away from the project page.

### F-4 Knowledge Ingestion and Management

- Users can add project sources from files and web URLs.
- The knowledge page supports project filtering, query filtering, preview, refresh, archive/restore, delete, and web source editing.
- Project pages show current source counts and can open the knowledge page in the current project context.

### F-5 Advanced Session Actions

- A turn can opt into deep research.
- A turn can opt into web supplementation when the project allows external evidence.
- Latest actionable assistant answers support saving a summary card.
- Sessions support generating a report card when a recent actionable answer exists.

### F-6 Settings

- The settings page exposes model configuration for LLM, embeddings, and reranker behavior.
- API keys are masked in the UI and not echoed back as plaintext values.
- Settings persist through the structured application state system rather than relying only on environment variables.

### F-7 Local-First Retrieval and Memory Runtime

- The backend uses SQLite for structured state and Qdrant for vector retrieval by default.
- Retrieval uses lexical and semantic retrieval with fusion and optional reranking.
- Session and project memory entries are maintained for continuity.
- Cleanup routines remove old archived/deleted data without blocking API startup.

## Near-Term Direction

- Keep the product direction unchanged: project-scoped, chat-first, local-first research workbench
- Confirm the V7 UI direction as the current near-term frontend track:
  - lighter reading-focused visual system
  - flatter project sidebar with less metadata density
  - roomier chat column and aligned composer column
  - lighter branded top navigation rather than a heavy dark shell
