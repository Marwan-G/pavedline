// Minimum supported app version (spec 11.4). The API sends `X-Min-App-Version` (plain MAJOR.MINOR.PATCH) on every
// response; an app older than that shows a blocking update screen.
export type Version = readonly [number, number, number]

const PLAIN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/

export function parseVersion(text: string | null | undefined): Version | null {
  const m = PLAIN.exec((text ?? '').trim())
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null
}

/** True only when both versions parse and `current` is older than `minimum`. A missing or malformed header never blocks. */
export function isBelowMinimum(current: string, minimum: string | null | undefined): boolean {
  const a = parseVersion(current)
  const b = parseVersion(minimum)
  if (!a || !b) return false
  for (let i = 0; i < 3; i++) {
    const x = a[i] as number
    const y = b[i] as number
    if (x !== y) return x < y
  }
  return false
}
