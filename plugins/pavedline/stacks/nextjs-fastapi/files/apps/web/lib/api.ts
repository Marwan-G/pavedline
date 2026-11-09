import 'server-only'
import { getHealth, type HealthResult } from '@app/api-client'

/** The API's address inside the cluster (a Service URL); set per environment by the chart. Never exposed to the browser. */
export function apiInternalUrl(): string | undefined {
  return process.env.API_INTERNAL_URL
}

export async function apiHealth(): Promise<HealthResult> {
  const base = apiInternalUrl()
  if (!base) return { ok: false, reason: 'API_INTERNAL_URL is not set' }
  return getHealth(base)
}
