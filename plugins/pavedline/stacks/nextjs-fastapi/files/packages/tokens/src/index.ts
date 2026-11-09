export { css, tokens } from './generated'

/** `var(--color-background)` for the token `color-background`. */
export function cssVar(name: string): string {
  return `var(--${name})`
}
