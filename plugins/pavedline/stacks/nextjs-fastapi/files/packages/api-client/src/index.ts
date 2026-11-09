import createClient, { type Client } from 'openapi-fetch'
import type { paths } from './generated/schema'

export type { components, paths } from './generated/schema'

/** The typed client for every operation in docs/api/openapi.yaml. */
export function createApiClient(
  baseUrl: string,
  init?: { headers?: Record<string, string> },
): Client<paths> {
  return createClient<paths>({ baseUrl, headers: init?.headers })
}

/** `/healthz` is a probe, not part of the contract (the API leaves it out of its OpenAPI document), so it is typed by hand. */
export type Health = { data: { status: 'ok' } }

export type HealthResult = { ok: true; status: string } | { ok: false; reason: string }

/** Ask the API whether it is up. Never throws: the caller renders the result. */
export async function getHealth(
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
  timeoutMs = 2000,
): Promise<HealthResult> {
  try {
    const res = await fetchImpl(new URL('/healthz', baseUrl), {
      cache: 'no-store',
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (!res.ok) return { ok: false, reason: `HTTP ${res.status}` }
    const body = (await res.json()) as Partial<Health>
    const status = body.data?.status
    return typeof status === 'string'
      ? { ok: true, status }
      : { ok: false, reason: 'unexpected response' }
  } catch {
    return { ok: false, reason: 'unreachable' }
  }
}
