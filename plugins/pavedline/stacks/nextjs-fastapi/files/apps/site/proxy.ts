import { type NextRequest, NextResponse } from 'next/server'
import { isIndexable } from './lib/robots'

// Runs on every request and reads the environment at runtime: a non-public origin sends X-Robots-Tag: noindex.
export function proxy(_request: NextRequest) {
  const response = NextResponse.next()
  if (!isIndexable()) response.headers.set('X-Robots-Tag', 'noindex, nofollow')
  return response
}
