import { resolve } from 'node:path'
import type { NextConfig } from 'next'

// Every response of the web app: a non-public origin (the website is the public one), so it is never indexed.
// script-src and style-src allow 'unsafe-inline' because Next.js inlines its bootstrap script and a nonce would force
// every page to render per request; everything else is same-origin only.
export const securityHeaders = [
  { key: 'X-Robots-Tag', value: 'noindex, nofollow' },
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; '),
  },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
]

const config: NextConfig = {
  output: 'standalone',
  // The monorepo root, so the standalone server traces the workspace packages.
  outputFileTracingRoot: resolve(import.meta.dirname, '../..'),
  transpilePackages: ['@app/api-client', '@app/glossary', '@app/tokens'],
  poweredByHeader: false,
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }]
  },
}

export default config
