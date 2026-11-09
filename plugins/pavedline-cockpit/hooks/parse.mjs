// Pure parsing of the Pavedline records. No I/O: the caller hands the texts in.
// Read-only by construction: nothing here touches a file, a shell or the network.

export const MAX_LINE = 160
export const MAX_READ = 64 * 1024

// Drop ESC sequences (CSI, OSC, others) and C0/C1 control characters.
const ESC_SEQ = /\x1b\][^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c)?|\x1b\[[0-?]*[ -\/]*[@-~]|\x9b[0-?]*[ -\/]*[@-~]|\x1b[@-_]?/g
const CONTROL = /[\x00-\x08\x0b-\x1f\x7f-\x9f]/g

export function clean(line) {
  const t = String(line).replace(ESC_SEQ, '').replace(CONTROL, '')
  return t.length > MAX_LINE ? t.slice(0, MAX_LINE - 1) + '\u2026' : t
}

// A Pavedline project's STATE.md carries the template's STEP and OWNER fields.
export function isProject(stateText) {
  return typeof stateText === 'string' && /^STEP:/m.test(stateText) && /^OWNER:/m.test(stateText)
}

// True when realPath is strictly inside realRoot (both already resolved).
export function isInside(realRoot, realPath) {
  if (typeof realRoot !== 'string' || typeof realPath !== 'string' || !realRoot || !realPath) return false
  if (realPath.split('/').includes('..')) return false
  const root = realRoot.endsWith('/') ? realRoot : realRoot + '/'
  return realPath.startsWith(root) && realPath.length > root.length
}

const NONE = /^(none|-|n\/a)?$/i

function field(text, name) {
  const m = text.match(new RegExp('^' + name + ':[ \\t]*(.*)$', 'm'))
  return m ? m[1].trim() : null
}

// The first SLICES IN FLIGHT entry's branch, or null. An entry is
// `branch · worktree · owner`, on the field's own line or on an indented `- ` line below it.
export function sliceBranch(stateText) {
  if (typeof stateText !== 'string') return null
  const lines = stateText.split(/\r?\n/)
  const at = lines.findIndex(l => /^SLICES IN FLIGHT:/.test(l))
  if (at < 0) return null
  const inline = lines[at].replace(/^SLICES IN FLIGHT:/, '').trim()
  if (!NONE.test(inline)) return inline.split('·')[0].trim() || null
  for (const l of lines.slice(at + 1)) {
    if (!/^\s/.test(l)) break
    const item = l.match(/^\s+-\s+(.*)$/)
    if (!item || /^format when used/i.test(item[1])) continue
    return item[1].split('·')[0].trim() || null
  }
  return null
}

// Candidate hand-off paths for a branch, relative to the project. Unsafe names give none.
export function handoffPaths(branch) {
  if (!branch || /(^|\/)\.\.(\/|$)|^\/|\\|\0/.test(branch)) return []
  const flat = branch.replace(/\//g, '-')
  return flat === branch ? [`handoff/${branch}.md`] : [`handoff/${branch}.md`, `handoff/${flat}.md`]
}

export function openWaiting(waitingText) {
  if (typeof waitingText !== 'string') return { count: 0, titles: [] }
  const items = waitingText.split(/\r?\n/).filter(l => /^- F\d+\b/.test(l))
  const titles = items.slice(0, 3).map(l => {
    const [id, what] = l.replace(/^- /, '').split('·').map(s => s.trim())
    return what ? `${id} ${what}` : id
  })
  return { count: items.length, titles }
}

// files: { 'STATE.md': text|null, 'WAITING.md': text|null, handoff: { [branch]: text } }
// Returns the lines to show; never throws.
const NO_PROJECT = ['no Pavedline project here']

export function summarize(files) {
  try {
    const state = files && typeof files['STATE.md'] === 'string' ? files['STATE.md'].slice(0, MAX_READ) : null
    if (!isProject(state)) return NO_PROJECT
    const out = []
    for (const k of ['STEP', 'WAVE', 'NEXT']) {
      const v = field(state, k)
      if (v) out.push(`${k} ${v}`)
    }
    const branch = sliceBranch(state)
    if (branch) {
      out.push(`SLICE ${branch}`)
      const text = files.handoff && files.handoff[branch]
      if (typeof text === 'string') {
        const gates = text.slice(0, MAX_READ).split(/\r?\n/).filter(l => /^\s*Gates:/.test(l))
        if (gates.length) out.push(gates[gates.length - 1].trim())
      }
    }
    const w = openWaiting(typeof files['WAITING.md'] === 'string' ? files['WAITING.md'].slice(0, MAX_READ) : null)
    if (w.count > 0) {
      out.push(`WAITING ${w.count} open`)
      for (const t of w.titles) out.push(`  ${t}`)
    }
    return out.map(clean)
  } catch {
    return NO_PROJECT
  }
}
