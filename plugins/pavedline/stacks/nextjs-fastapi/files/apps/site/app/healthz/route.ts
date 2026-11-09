// The site pod's own probe (liveness and readiness).
export const dynamic = 'force-dynamic'

export function GET() {
  return Response.json({ data: { status: 'ok' } })
}
