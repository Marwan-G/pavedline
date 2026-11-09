import { terms } from './terms'

export type TermKey = keyof typeof terms

/** The label for a glossary term; a typo in the key is a type error. */
export function term(key: TermKey): string {
  return terms[key]
}

export { terms }
