export const MIN_VERSION_HEADER = 'X-Min-App-Version'

export type Health =
  | { state: 'ok'; minAppVersion: string | null }
  | { state: 'error'; minAppVersion: string | null; reason: string }

export type FetchLike = (url: string, init?: { signal?: AbortSignal }) => Promise<Response>

/** Reads `<baseUrl>/healthz`. Never throws: a failure is a state the screen shows. The version header is read on errors too. */
export async function fetchHealth(
  baseUrl: string,
  fetcher: FetchLike = fetch,
  timeoutMs = 8000,
): Promise<Health> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetcher(`${baseUrl.replace(/\/+$/, '')}/healthz`, { signal: controller.signal })
    const minAppVersion = res.headers.get(MIN_VERSION_HEADER)
    if (!res.ok) return { state: 'error', minAppVersion, reason: `HTTP ${res.status}` }
    return { state: 'ok', minAppVersion }
  } catch (error) {
    const reason = error instanceof Error && error.name === 'AbortError' ? 'timeout' : 'unreachable'
    return { state: 'error', minAppVersion: null, reason }
  } finally {
    clearTimeout(timer)
  }
}
