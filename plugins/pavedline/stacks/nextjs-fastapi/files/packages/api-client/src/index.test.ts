import { describe, expect, it } from 'vitest'
import { createApiClient, getHealth } from './index'

const json = (body: unknown, status = 200) =>
  (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

describe('getHealth', () => {
  it('reads the status of the API', async () => {
    expect(await getHealth('http://api', json({ data: { status: 'ok' } }))).toEqual({
      ok: true,
      status: 'ok',
    })
  })
  it('reports an HTTP error', async () => {
    expect(await getHealth('http://api', json({}, 503))).toEqual({ ok: false, reason: 'HTTP 503' })
  })
  it('reports an unexpected body', async () => {
    expect(await getHealth('http://api', json({ nope: 1 }))).toEqual({
      ok: false,
      reason: 'unexpected response',
    })
  })
  it('never throws when the API is down', async () => {
    const down = (async () => {
      throw new Error('boom')
    }) as unknown as typeof fetch
    expect(await getHealth('http://api', down)).toEqual({ ok: false, reason: 'unreachable' })
  })
})

describe('createApiClient', () => {
  it('builds a client with the base URL', () => {
    expect(typeof createApiClient('http://api').GET).toBe('function')
  })
})
