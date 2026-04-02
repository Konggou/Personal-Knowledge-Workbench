# Frontend Visual System

Last Updated: 2026-04-02 16:40 Asia/Shanghai
Related IDs: F-1, F-2, F-3, F-4, F-5, FLOW-1, FLOW-2, FLOW-4, FLOW-5

## Visual Direction

- Chat-first research workspace
- Editorial reading emphasis
- Warm neutral surfaces with amber accent
- Low-cardinality layout hierarchy rather than many competing panels

## Current Confirmed Direction

- V7 is the confirmed near-term visual track
- The current branch direction shifts the product from a heavy dark shell toward a lighter reading-focused interface
- The top navigation remains branded, but lighter and less visually dominant than the older dark glass treatment

## Tokens and Themes

- Root visual tokens live in `apps/web/src/app/globals.css`
- Shared app-shell styling lives in `apps/web/src/components/shell/app-shell.module.css`
- Project-page-specific density and layout live in `apps/web/src/components/projects/project-chat-client.module.css`

## Layout Rules

- The project page keeps:
  - top navigation
  - left sidebar
  - central chat stage
- No permanent right-side knowledge column on the project page
- The sidebar can collapse into a narrow rail and must increase usable center width when collapsed
- The chat column and composer column stay aligned

## Sidebar Rules

- Projects are rendered as list rows rather than stacked card blocks
- Non-current projects stay collapsed in the project page sidebar
- The current project shows sessions in a lighter-density nested list
- Session actions belong in an overflow menu, not in always-visible inline buttons

## Message and Composer Rules

- Assistant messages prioritize readability and evidence access
- User messages remain visually distinct but should not dominate the page width
- Composer actions remain capsule-style controls tied to the current session turn
- Summary and report actions remain session-native

## Visual Risks to Watch

- Full `vitest run` currently hangs in this repo, so visual regressions need browser validation in addition to targeted tests
- Theme changes are global because most pages consume shared root tokens
