import { isBelowMinimum, parseVersion } from '../version'

describe('parseVersion', () => {
  it('reads plain semver', () => expect(parseVersion('1.20.3')).toEqual([1, 20, 3]))
  it.each(['', '1', '1.2', 'v1.2.3', '1.2.3-beta', '01.2.3', '1.2.x', null, undefined])('rejects %p', (v) =>
    expect(parseVersion(v)).toBeNull(),
  )
})

describe('isBelowMinimum', () => {
  it.each([
    ['1.0.0', '1.0.1', true],
    ['1.9.9', '2.0.0', true],
    ['1.2.3', '1.3.0', true],
    ['1.0.0', '1.0.0', false],
    ['2.0.0', '1.9.9', false],
    ['1.10.0', '1.9.0', false],
    ['0.1.0', '0.0.0', false],
  ])('%s vs minimum %s -> %s', (current, min, expected) => expect(isBelowMinimum(current, min)).toBe(expected))

  it('never blocks on a missing or malformed header', () => {
    expect(isBelowMinimum('1.0.0', null)).toBe(false)
    expect(isBelowMinimum('1.0.0', 'soon')).toBe(false)
    expect(isBelowMinimum('not-a-version', '1.0.0')).toBe(false)
  })
})
