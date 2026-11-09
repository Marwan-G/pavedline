// Pavedline cockpit: a read-only pane and /pavedline-status. Reads STATE.md, WAITING.md and
// the open slice's handoff file from the project directory. No shell, no network, no writes.
import { atom, read, update } from 'claude-code'
import { MAX_READ, handoffPaths, isInside, isProject, sliceBranch, summarize } from './parse.mjs'

const PANE = 'pavedline-cockpit'
const tick = atom({ plugin: 'pavedline-cockpit', key: 'tick' }, 0, { shape: 'tick-1' })

// Reads one project file, bounded: the path must resolve (symlinks included) to inside the
// project root, and only the first MAX_READ characters are kept.
async function readText($, root, realRoot, rel) {
  try {
    const abs = `${root}/${rel}`
    const st = await $.fs.stat(abs, { resolve: true })
    if (!isInside(realRoot, st.realPath) || st.kind !== 'file') return null
    return (await $.fs.read(abs)).slice(0, MAX_READ)
  } catch {
    return null
  }
}

async function load($) {
  try {
    const root = await $.session.root()
    const realRoot = (await $.fs.stat(root, { resolve: true })).realPath
    const state = await readText($, root, realRoot, 'STATE.md')
    const handoff = {}
    const branch = sliceBranch(state)
    for (const p of handoffPaths(branch)) {
      const text = await readText($, root, realRoot, p)
      if (text !== null) {
        handoff[branch] = text
        break
      }
    }
    const waiting = await readText($, root, realRoot, 'WAITING.md')
    return { project: isProject(state), lines: summarize({ 'STATE.md': state, 'WAITING.md': waiting, handoff }) }
  } catch {
    return { project: false, lines: ['no Pavedline project here'] }
  }
}

export const register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'pavedline-status',
      description: 'Print the Pavedline step, wave, next action, open slice gates and waiting items',
    })
    // The pane opens only in a Pavedline project.
    if ((await load($)).project) void $.ui.open({ id: PANE, title: 'Pavedline' })
    return next(e)
  })

  on('command.run', { command: 'pavedline-status' }, async $ => ({
    text: (await load($)).lines.join('\n'),
  }))

  // Redraw when a turn ends: the records change as turns do. No timer, no polling.
  on('turn.complete', async ($, e, next) => {
    await update($, tick, n => n + 1)
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e, next) => {
    const { Box, Text } = $.ui.resolve(e)
    await read($, tick)
    const { project, lines } = await load($)
    if (!project) return next(e) // elsewhere: nothing is drawn
    return Box({
      flexDirection: 'column',
      children: lines.map(l => Text({ dimColor: l.startsWith('  ') || l.startsWith('no '), children: [l] })),
    })
  })
}
