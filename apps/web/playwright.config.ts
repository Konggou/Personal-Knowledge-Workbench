import { defineConfig } from "@playwright/test";

const isCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  retries: isCi ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3010",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node e2e/start-api.mjs",
      port: 8011,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "node e2e/fixture-server.mjs",
      port: 3311,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "corepack pnpm dev --port 3010",
      port: 3010,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8011",
        NEXT_DIST_DIR: ".next-e2e",
      },
    },
  ],
  projects: [
    {
      name: "edge",
      use: {
        browserName: "chromium",
        channel: "msedge",
        viewport: {
          width: 1440,
          height: 960,
        },
      },
    },
  ],
});
