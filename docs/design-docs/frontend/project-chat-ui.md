# Frontend Design: Project Chat UI

Last Updated: 2026-04-02 16:40 CST

Related IDs: `F-2`, `F-4`, `F-5`, `F-6`, `F-8`, `FLOW-3`, `FLOW-5`, `FLOW-6`, `FLOW-7`, `FLOW-8`

## Layout Contract

- The page is a two-column layout:
  - left sidebar for project tree and session selection
  - main chat stage for the selected project/session
- Sidebar collapsed state must shrink into a narrow rail that makes the center column genuinely wider.
- The message column and composer column must share the same center axis.

## Sidebar Contract

- Project rows show:
  - project badge
  - project name
  - source count only
- Only the current project expands into session rows on the project page.
- Session rows show title only by default.
- Session rename/delete actions live in an overflow menu instead of persistent inline action text.
- Overflow controls must be keyboard reachable and dismissible.

## Composer Contract

- Required actions:
  - Add Material
  - text input
  - Deep Research
  - Web Supplement
  - Generate Report
  - Send
- `Deep Research` and `Web Supplement` state are remembered per session.
- Add Material supports web URLs and files only.

## Message Stream Contract

- User message appears immediately.
- Assistant placeholder appears immediately.
- Streamed delta content updates the placeholder in place.
- Final source bubble appears only after the final answer resolves.
- Summary and report cards render inline and are treated as conversation artifacts.

## Source Layer Contract

- The source bubble reflects the final evidence set only.
- Expanded source lists show source titles before detailed preview content.
- Detailed preview opens in an overlay sheet, not a separate route.
- Web-supplemented sources can be saved into project knowledge from the inline evidence list.

## V7 Visual Rules

- Theme: light reading-first surfaces with dark text
- Sidebar: list-like instead of stacked cards
- Project density: reduced metadata per row
- Reading width: wider than the earlier `800px` center column constraint
- Top navigation: lighter and less visually dominant while retaining brand identity

## Non-Negotiable UI Guardrails

- Keep the product chat-first.
- Do not reintroduce `/tasks`, `/search`, `/assets`, or task-detail mental models.
- Do not add a permanent right-side knowledge panel.
- Do not move summaries or reports to standalone pages.
