import { describe, expect, it } from 'vitest'
import { securityHeaders } from '../next.config'
import { statusView } from './status'

describe('statusView', () => {
  it('shows the API as up', () => {
    expect(statusView({ ok: true, status: 'ok' })).toEqual({ label: 'API is up', tone: 'ok' })
  })
  it('shows another status as down', () => {
    expect(statusView({ ok: true, status: 'degraded' }).tone).toBe('down')
  })
  it('shows a failure with its reason', () => {
    expect(statusView({ ok: false, reason: 'unreachable' })).toEqual({
      label: 'API is not reachable (unreachable)',
      tone: 'down',
    })
  })
})

describe('security headers', () => {
  const header = (k: string) => securityHeaders.find((h) => h.key === k)?.value ?? ''
  it('are never indexed and framed by nobody', () => {
    expect(header('X-Robots-Tag')).toContain('noindex')
    expect(header('Content-Security-Policy')).toContain("frame-ancestors 'none'")
    expect(header('Content-Security-Policy')).toContain("default-src 'self'")
    expect(header('X-Content-Type-Options')).toBe('nosniff')
    expect(header('Referrer-Policy')).not.toBe('')
  })
})
