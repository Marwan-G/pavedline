// A stand-in for the API during the browser test: answers /healthz like the FastAPI service does.
import { createServer } from 'node:http'

createServer((req, res) => {
  if (req.url === '/healthz') {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ data: { status: 'ok' } }))
  } else {
    res.writeHead(404).end()
  }
}).listen(Number(process.env.STUB_API_PORT ?? 4010), '127.0.0.1')
