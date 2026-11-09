import { defineConfig } from 'vitest/config'

// Playwright specs live in e2e/ and run with `pnpm e2e`, not here.
export default defineConfig({ test: { include: ['lib/**/*.test.ts', 'app/**/*.test.ts'] } })
