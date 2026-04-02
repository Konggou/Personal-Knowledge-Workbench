# V7 Light Theme Refresh

Last Updated: 2026-04-02 16:40 Asia/Shanghai
Status: validating
Related IDs: F-1, F-2, F-3, FLOW-1, FLOW-4, FLOW-5

## Goal

Refresh the frontend visual system toward a lighter reading-focused interface while preserving the existing project/session/source product model.

## Scope

- In scope:
  - global light-theme tokens
  - lighter branded top navigation
  - roomier project chat layout
  - flatter project sidebar
  - session overflow actions in the sidebar
  - targeted frontend tests for the new sidebar behavior
- Out of scope:
  - backend API redesign
  - route model changes
  - product scope expansion

## Steps

1. Replace the heavy dark token system with a lighter warm editorial token system.
2. Update app-shell presentation to a lighter branded navigation bar.
3. Rework the project page sidebar and chat density.
4. Update affected page-level CSS modules for consistency.
5. Verify targeted frontend type checks and tests.

## Verification Performed

- `corepack pnpm --dir apps/web typecheck`
- `apps/web/.\node_modules\.bin\vitest.cmd run src/components/projects/project-chat-client.test.tsx`
- `apps/web/.\node_modules\.bin\vitest.cmd run src/components/workspace/workspace-page-client.test.tsx src/components/settings/settings-page-client.test.tsx src/components/shell/app-shell.test.tsx`

## Known Issues

- Full `vitest run` currently hangs in this repo and was not used as a passing verification signal.
- `knowledge-page-client.test.tsx` also timed out during attempted standalone execution and still needs investigation.

## Exit Criteria

- Targeted frontend regressions remain green.
- The new docs describe V7 as the confirmed near-term UI direction.
- Remaining verification gaps are explicitly tracked rather than implied away.

## Immediate Next Actions

- Run browser-level visual checks for the updated light theme and project page density.
- Investigate why full Vitest execution hangs.
