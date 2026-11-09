import { fetchHealth, type FetchLike } from '../health'

const reply = (status: number, headers: Record<string, string> = {}): FetchLike => async () =>
  new Response('{}', { status, headers })

describe('fetchHealth', () => {
  it('is ok and carries the minimum version header', async () => {
    expect(await fetchHealth('http://api.test/', reply(200, { 'X-Min-App-Version': '2.0.0' }))).toEqual({
      state: 'ok',
      minAppVersion: '2.0.0',
    })
  })

  it('calls /healthz under the base URL without a double slash', async () => {
    const seen: string[] = []
    await fetchHealth('http://api.test///', async (url) => {
      seen.push(url)
      return new Response('{}')
    })
    expect(seen).toEqual(['http://api.test/healthz'])
  })

  it('reports an HTTP error and still reads the header', async () => {
    expect(await fetchHealth('http://api.test', reply(503, { 'X-Min-App-Version': '3.0.0' }))).toEqual({
      state: 'error',
      minAppVersion: '3.0.0',
      reason: 'HTTP 503',
    })
  })

  it('reports a network failure without throwing', async () => {
    const down: FetchLike = async () => {
      throw new TypeError('network')
    }
    expect(await fetchHealth('http://api.test', down)).toEqual({
      state: 'error',
      minAppVersion: null,
      reason: 'unreachable',
    })
  })
})
