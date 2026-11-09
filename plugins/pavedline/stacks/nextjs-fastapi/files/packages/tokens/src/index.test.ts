import { describe, expect, it } from 'vitest'
import { css, cssVar, tokens } from './index'

describe('tokens', () => {
  it('exposes light and dark with the same names', () => {
    expect(Object.keys(tokens.light).sort()).toEqual(Object.keys(tokens.dark).sort())
  })
  it('emits a variable for every token, in :root', () => {
    for (const name of Object.keys(tokens.light)) expect(css).toContain(`--${name}:`)
    if (Object.keys(tokens.light).length > 0) expect(css).toContain(':root')
  })
  it('builds var() references', () => {
    expect(cssVar('color-background')).toBe('var(--color-background)')
  })
})
