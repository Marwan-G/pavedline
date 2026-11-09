// The in-image boot check: start the standalone server and require /healthz to answer. An image whose server cannot
// start fails the build, not the first pod. Usage: node boot-check.mjs <path-to-server.js> [expected-x-robots-tag-substring]
import { spawn } from 'node:child_process'

const [server, robots] = process.argv.slice(2)
if (!server) {
  console.error('usage: node boot-check.mjs <server.js> [x-robots-tag-substring]')
  process.exit(2)
}
const port = 3987
const child = spawn(process.execPath, [server], {
  env: { ...process.env, PORT: String(port), HOSTNAME: '127.0.0.1', NODE_ENV: 'production' },
  stdio: ['ignore', 'inherit', 'inherit'],
})
let exited = false
child.on('exit', () => {
  exited = true
})

async function main() {
  for (let i = 0; i < 60; i++) {
    if (exited) throw new Error('the server exited during the boot check')
    try {
      const res = await fetch(`http://127.0.0.1:${port}/healthz`)
      if (res.status !== 200) throw new Error(`/healthz answered ${res.status}`)
      const body = await res.json()
      if (body?.data?.status !== 'ok')
        throw new Error('/healthz body is not {"data":{"status":"ok"}}')
      if (robots && !(res.headers.get('x-robots-tag') ?? '').includes(robots)) {
        throw new Error(`x-robots-tag does not contain ${robots}`)
      }
      console.log('boot check: ok')
      return
    } catch (err) {
      if (
        err instanceof Error &&
        !/fetch failed|ECONNREFUSED/.test(`${err.message}${err.cause ?? ''}`)
      )
        throw err
      await new Promise((r) => setTimeout(r, 500))
    }
  }
  throw new Error('the server did not answer /healthz within 30 s')
}

main()
  .then(() => {
    process.exitCode = 0
  })
  .catch((err) => {
    console.error(`boot check failed: ${err.message}`)
    process.exitCode = 1
  })
  .finally(() => child.kill('SIGKILL'))
