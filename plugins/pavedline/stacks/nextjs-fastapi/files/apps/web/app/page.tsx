import { apiHealth } from '@/lib/api'
import { statusView } from '@/lib/status'

// Rendered on the server for each request: the status comes from the API inside the cluster, so the browser never
// calls the API (no CORS) and never learns its address.
export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const view = statusView(await apiHealth())
  return (
    <main>
      <h1>App</h1>
      <p data-testid="api-status" data-tone={view.tone}>
        {view.label}
      </p>
    </main>
  )
}
