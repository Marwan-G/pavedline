import { describe, expect, it } from 'vitest'
import { isIndexable, robotsFor, siteOrigin } from './robots'

describe('robots policy', () => {
  it('is disallow-all unless SITE_INDEXABLE is exactly "true"', () => {
    for (const env of [
      {},
      { SITE_INDEXABLE: 'false' },
      { SITE_INDEXABLE: '1' },
      { SITE_INDEXABLE: 'TRUE' },
    ]) {
      expect(isIndexable(env)).toBe(false)
      expect(robotsFor(env)).toEqual({ rules: [{ userAgent: '*', disallow: '/' }] })
    }
  })
  it('allows and links the sitemap on the public origin', () => {
    const r = robotsFor({ SITE_INDEXABLE: 'true', SITE_ORIGIN: 'https://example.com/' })
    expect(r.rules[0]).toEqual({ userAgent: '*', allow: '/' })
    expect(r.sitemap).toBe('https://example.com/sitemap.xml')
  })
  it('adds a disallow rule for AI crawlers when the policy says so', () => {
    const r = robotsFor({ SITE_INDEXABLE: 'true', AI_CRAWLER_POLICY: 'disallow' })
    expect(JSON.stringify(r.rules)).toContain('GPTBot')
  })
  it('trims a trailing slash from the origin', () => {
    expect(siteOrigin({ SITE_ORIGIN: 'https://example.com//' })).toBe('https://example.com')
  })
})
