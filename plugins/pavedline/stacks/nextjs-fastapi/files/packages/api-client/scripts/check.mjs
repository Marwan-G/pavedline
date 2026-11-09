// Fail when the committed generated client is not what the generator makes from docs/api/openapi.yaml today.
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const committed = resolve(here, '../src/generated/schema.d.ts')
const dir = mkdtempSync(join(tmpdir(), 'api-client-'))
try {
  const fresh = join(dir, 'schema.d.ts')
  const r = spawnSync(process.execPath, [join(here, 'generate.mjs'), fresh], { stdio: 'inherit' })
  if (r.status !== 0) process.exit(r.status ?? 1)
  if (readFileSync(fresh, 'utf8') !== readFileSync(committed, 'utf8')) {
    console.error(
      'api-client: src/generated/schema.d.ts is out of date. Run: pnpm --filter @app/api-client generate',
    )
    process.exit(1)
  }
  console.log('api-client: generated client is current')
} finally {
  rmSync(dir, { recursive: true, force: true })
}
