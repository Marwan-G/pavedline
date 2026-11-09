# Plans

One file per wave: `<YYYY-MM-DD>-wave-<n>.md`, with its `.dot` and `.svg`. A slice is a heading
`### Slice <wave>.<n>: <title>` followed by these lines:
`Tests: AT-001, AT-004` · `Surfaces: web, api` · `Branch: <name>` · `Depends on: <slice ids or none>`
A header may say `Deferred: AT-005, AT-006 (later waves)`; a later wave that proves an old test again adds `Re-tests: AT-001`.
Every acceptance test maps to exactly one slice. `plan_graph.py check` finds the gaps; a merged commit's subject starts `Slice <id>` (or has a `Slice: <id>` trailer).
The integration wave is one plan with the header line `Wave: integration` and slices `### Slice int.<n>:` (`Tests: none`); its evidence is a header line `Verified: local — <date>, <what was seen>` (above the first slice).
`plan_graph.py status` prints `integration wave: not due | due | planned | done`; step 12 starts only on `integration wave: done`.
