// The web pod's own probe (liveness and readiness). It does not call the API: an API outage must not restart web pods.
export const dynamic = 'force-dynamic'

export function GET() {
  return Response.json({ data: { status: 'ok' } })
}
