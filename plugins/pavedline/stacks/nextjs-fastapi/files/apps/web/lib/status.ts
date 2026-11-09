import type { HealthResult } from '@app/api-client'

export type StatusView = { label: string; tone: 'ok' | 'down' }

/** The words a person reads for the API's health. */
export function statusView(result: HealthResult): StatusView {
  if (result.ok && result.status === 'ok') return { label: 'API is up', tone: 'ok' }
  if (result.ok) return { label: `API reports: ${result.status}`, tone: 'down' }
  return { label: `API is not reachable (${result.reason})`, tone: 'down' }
}
