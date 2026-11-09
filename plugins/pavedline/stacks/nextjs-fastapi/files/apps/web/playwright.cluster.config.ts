import { defineConfig } from '@playwright/test'

// The same checks as e2e/home.spec.ts (status text, axe WCAG 2.2 AA, headers) against an ALREADY RUNNING deployment,
// such as the local cluster in CI. Nothing is started here. Run:
//   E2E_BASE_URL=http://app.localtest.me:8080 pnpm --filter @app/web exec playwright test -c playwright.cluster.config.ts
const baseURL = process.env.E2E_BASE_URL
if (!baseURL)
  throw new Error(
    'E2E_BASE_URL is required (the deployed web app, e.g. http://app.localtest.me:8080)',
  )

export default defineConfig({
  testDir: './e2e',
  testMatch: 'home.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})
