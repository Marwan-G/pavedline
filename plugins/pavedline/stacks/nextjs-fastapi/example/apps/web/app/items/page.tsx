import { createApiClient } from '@app/api-client'
import { term } from '@app/glossary'
import { apiInternalUrl } from '@/lib/api'

// The example's contract has GET /v1/items. The browser never calls the API: this page fetches on the server.
// Without a signed-in user the API answers 401 (a later step adds sign-in), and the page says so.
export const dynamic = 'force-dynamic'

export default async function ItemsPage() {
  const base = apiInternalUrl()
  if (!base)
    return (
      <main>
        <h1>{term('items')}</h1>
        <p>The API address is not configured.</p>
      </main>
    )
  const { data, response } = await createApiClient(base).GET('/v1/items', {})
  return (
    <main>
      <h1>{term('items')}</h1>
      {data ? (
        <ul>
          {data.data.map((item) => (
            <li key={item.id}>
              {item.name}: {item.price_minor} {item.currency}
            </li>
          ))}
        </ul>
      ) : (
        <p>The list needs a signed-in user (the API answered {response.status}).</p>
      )}
    </main>
  )
}
