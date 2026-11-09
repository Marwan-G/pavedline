import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('the home page shows the API status, fetched on the server', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('api-status')).toHaveText('API is up')
})

test('the home page has no WCAG 2.2 AA violations', async ({ page }) => {
  await page.goto('/')
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  expect(violations).toEqual([])
})

test('every response is noindex with a disallow-all robots.txt', async ({ page, request }) => {
  const res = await page.goto('/')
  expect(res?.headers()['x-robots-tag']).toContain('noindex')
  expect(res?.headers()['content-security-policy']).toContain("default-src 'self'")
  const robots = await request.get('/robots.txt')
  expect(await robots.text()).toContain('Disallow: /')
})
