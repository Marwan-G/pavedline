import { defineConfig } from '@playwright/test'

// The test runs against the real standalone build (`pnpm build` first), not the dev server, with a stub API beside it.
const web = Number(process.env.E2E_WEB_PORT ?? 3100)
const api = Number(process.env.E2E_API_PORT ?? 4010)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: `http://127.0.0.1:${web}` },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: [
    {
      command: 'node e2e/stub-api.mjs',
      url: `http://127.0.0.1:${api}/healthz`,
      env: { STUB_API_PORT: String(api) },
      reuseExistingServer: false,
    },
    {
      // the standalone server does not copy .next/static itself (the Dockerfile does)
      command:
        'sh -c "mkdir -p .next/standalone/apps/web/.next && cp -R .next/static .next/standalone/apps/web/.next/ && node .next/standalone/apps/web/server.js"',
      url: `http://127.0.0.1:${web}/healthz`,
      env: {
        PORT: String(web),
        HOSTNAME: '127.0.0.1',
        API_INTERNAL_URL: `http://127.0.0.1:${api}`,
      },
      reuseExistingServer: false,
    },
  ],
})
