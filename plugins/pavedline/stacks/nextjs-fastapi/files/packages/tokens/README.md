# @app/tokens

CSS variables and a typed object built from `docs/design/tokens.json`, the export of step 7.

Format: `{"light": {"color": {"background": "#ffffff"}}, "dark": {"color": {"background": "#0b0b0c"}}}`. Nested keys are
joined with `-` (`--color-background`). Light and dark must define the same names; the build fails otherwise.
`pnpm --filter @app/tokens build` writes `src/generated.ts`; `check` fails when the committed file is stale (CI).
`css` holds the `:root` block plus a `prefers-color-scheme: dark` block; the apps put it in a `<style>` element.
The package in `files/` ships an empty placeholder; the starter check overlays `example/docs/design/tokens.json`.
