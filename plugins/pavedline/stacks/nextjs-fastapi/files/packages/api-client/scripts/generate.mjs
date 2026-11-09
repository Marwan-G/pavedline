// Generate src/generated/schema.d.ts from the product's contract. Usage: node scripts/generate.mjs [out-file]
import { spawnSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const contract = resolve(here, '../../../docs/api/openapi.yaml')
const out = resolve(process.argv[2] ?? resolve(here, '../src/generated/schema.d.ts'))
const bin = resolve(here, '../node_modules/.bin/openapi-typescript')
const r = spawnSync(bin, [contract, '-o', out], { stdio: 'inherit' })
process.exit(r.status ?? 1)
