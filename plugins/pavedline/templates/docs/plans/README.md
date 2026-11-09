# Plans

One file per wave: `<YYYY-MM-DD>-wave-<n>.md`, with its `.dot` and `.svg`. A slice is a heading
`### Slice <wave>.<n>: <title>` followed by these lines:

`Tests: AT-001, AT-004` · `Surfaces: web, api` · `Branch: <name>` · `Depends on: <slice ids or none>`

A plan header may say `Deferred: AT-005, AT-006 (later waves)`: those tests are planned in a later wave.
A later wave that proves an old test again adds `Re-tests: AT-001`. Every acceptance test maps to exactly one slice.
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py check` finds the gaps; a merged commit's subject starts `Slice <id>` (or has a `Slice: <id>` trailer).
