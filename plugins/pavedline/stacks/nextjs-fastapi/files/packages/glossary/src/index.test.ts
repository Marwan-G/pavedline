import { describe, expect, it } from 'vitest'
import { term, terms } from './index'

describe('glossary', () => {
  it('has a non-empty label for every term', () => {
    for (const [key, label] of Object.entries<string>(terms)) {
      expect(label.trim(), key).not.toBe('')
    }
  })
  it('returns the label of a term', () => {
    for (const key of Object.keys(terms) as (keyof typeof terms)[])
      expect(term(key)).toBe(terms[key])
  })
})
