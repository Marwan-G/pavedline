import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'pavedline-cockpit',
  component: 'Pane',
  requestId: 'pavedline-cockpit',
  props: {
    title: 'Pavedline',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

const ROOT = '/work/proj'
const STATE = 'STEP: 3 — Spec\nOWNER: main\nWAVE: none\nSLICES IN FLIGHT: feature/x · wt · a\nNEXT: write the spec\n'

// A project at ROOT: `files` maps a project-relative name to its text; `links` maps a
// name to where its symlink really lands.
function project(on: any, files: Record<string, string>, links: Record<string, string> = {}, reads: string[] = []) {
  on('session.root', () => ({ value: ROOT }))
  on('fs.stat', (_: any, e: any) => {
    if (e.path === ROOT) return { value: { kind: 'dir', size: 0, mtimeMs: 0, isLink: false, realPath: ROOT } }
    const rel = e.path.slice(ROOT.length + 1)
    if (!(rel in files)) return Promise.reject(new Error('ENOENT'))
    return {
      value: { kind: 'file', size: 1, mtimeMs: 0, isLink: rel in links, realPath: links[rel] ?? e.path },
    }
  })
  on('fs.read', (_: any, e: any) => {
    reads.push(e.path)
    const rel = e.path.slice(ROOT.length + 1)
    return rel in files ? { value: files[rel] } : Promise.reject(new Error('ENOENT'))
  })
}

test('the pane shows the records, read from the session root', async ($, on) => {
  project(on, {
    'STATE.md': STATE,
    'WAITING.md': '- F1 · Log in · dash · unblocks push\n',
    'handoff/feature/x.md': 'Gates: TDD ✓ · review pending\n',
  })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /STEP 3/ }))?.text).toBe('STEP 3 — Spec')
  expect(await ui.find({ type: 'Text', text: /WAITING 1 open/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /Gates: TDD/ })).toBeTruthy()
  await ui.unmount()
})

test('a symlink that leaves the project is not read', async ($, on) => {
  project(
    on,
    { 'STATE.md': STATE, 'WAITING.md': '- F1 · Secret · x · y\n', 'handoff/feature/x.md': 'Gates: leaked\n' },
    { 'WAITING.md': '/etc/passwd', 'handoff/feature/x.md': '/work/proj-other/x.md' },
  )
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /STEP 3/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /Secret|WAITING/ })).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /leaked/ })).toBeFalsy()
  await ui.unmount()
})

test('a branch with .. never reads outside handoff/', async ($, on) => {
  const read: string[] = []
  project(on, { 'STATE.md': 'STEP: 1\nOWNER: o\nSLICES IN FLIGHT: ../../etc/passwd · w · a\n' }, {}, read)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.find({ type: 'Text' })
  expect(read.every(p => p.startsWith(ROOT + '/'))).toBe(true)
  expect(read.some(p => p.includes('..'))).toBe(false)
  await ui.unmount()
})

test('outside a Pavedline project nothing is drawn', async ($, on) => {
  project(on, { 'STATE.md': '# notes\nSTEP: 1\n' })
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

test('the command prints the summary, clean of escapes', async ($, on) => {
  project(on, { 'STATE.md': 'STEP: 2\nOWNER: o\nNEXT: go \x1b[2Jnow\n' })
  on('command.run', () => ({ text: 'unreached' }))
  const out = await $.command.run({ command: 'pavedline-status' })
  expect(JSON.stringify(out)).toContain('NEXT go now')
})
