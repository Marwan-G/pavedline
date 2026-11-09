# Contributing to Pavedline

Thanks for your interest. Pavedline is a Claude Code plugin marketplace; contributions are welcome.

## Ground rules

- Python code uses the standard library only and targets Python 3.10+.
- Run the tests with `python3 -m unittest discover -s tests -t .`.
- Plugin evals (optional, real model calls on your account): `scripts/run_evals.sh` runs `plugins/pavedline/evals` once per case with a $5 cap.
- Validate manifests with `claude plugin validate . --strict` and
  `claude plugin validate plugins/pavedline --strict`.
- Keep changes focused: one concern per pull request, with tests for new behavior.
- Do not commit secrets, local paths, or identifiers that belong to a private project.

## Trying a change locally

- Install the dependency plugins first (`superpowers`, `mattpocock-skills`, `product-management`, `figma`;
  `/pavedline:doctor` lists them, with `ui-ux-pro-max` and `impeccable` as optional). With a dependency missing, `claude --plugin-dir plugins/pavedline`
  silently loads nothing.
- Headless runs (`claude -p`): add `--add-dir <plugin dir>` so skills can read their own `references/` files
  ([permissions](https://code.claude.com/docs/en/permissions.md), checked 2026-11-08), and use
  `--output-format stream-json --verbose` so the session id appears first. macOS has no `timeout` command; do not rely on it.

## Running the starter check

Any change under `plugins/pavedline/stacks/` or `plugins/pavedline/templates/` must pass the starter check, which
generates a neutral product (`example`, all four surfaces, multi-tenant; answers in `tests/fixtures/starter-answers.json`)
and proves it builds, tests, boots and deploys:

```bash
scripts/starter_check.sh                 # all stages
scripts/starter_check.sh --stage static  # helm + Checkov, actionlint, records scripts (seconds)
scripts/starter_check.sh --stage unit    # pnpm and uv checks, both builds, Playwright + axe, API tests on a throwaway Postgres
scripts/starter_check.sh --stage cluster # kind + Argo CD deploy, must print `verified (local)`, then every hostname answers
scripts/starter_check.sh --keep          # keep the generated tree (its path is printed)
```

It needs Docker (Colima is fine), Node, `uv`, `kind`, `kubectl`, `helm`, `actionlint` and Graphviz (`dot`); nothing
else is installed for you and it never runs `sudo`. It prints one PASS or FAIL line per step with its time, cleans up
its Postgres container, kind cluster and temp directory on exit, and refuses any Kubernetes context that is not a
`kind-pavedline-*` one. It creates the cluster `pavedline-ci`, so it stops if one already exists. Expect about
five minutes with warm caches (the first run pulls images and packages: allow fifteen). The native mobile builds (Gradle for Android, Xcode for an unsigned iOS simulator build) run only in
CI, in `.github/workflows/starter-mobile.yml` (on changes to the stack pack and weekly; never a required check).

## Found a problem? Open an issue

Use [New issue](https://github.com/Marwan-G/pavedline/issues/new/choose) and pick **Bug report** or
**Feature request**. The form asks for the step, your versions and the `/pavedline:doctor` output, which is what we
need to reproduce it. Security problems go to [SECURITY.md](SECURITY.md), never to a public issue.

## Workflow

1. Open or pick an issue first, so the change is agreed before you write it.
2. Fork the repository and create a branch.
3. Write a failing test, make it pass, and keep the suite green.
4. Open a pull request that links the issue (`Fixes #12`) and fills in the template, including which human reviewed
   the diff.

## How pull requests are reviewed

1. **CI runs on every pull request**: tests, lint, secret scan, diagram checks, plugin validation and a full local
   cluster test (kind, Argo CD, CloudNativePG, Postgres). For a first-time contributor, the maintainer starts CI after
   a first look.
2. **The maintainer reviews it locally with Claude Code**: reads the diff before running anything, tests it in a
   separate checkout, and runs an independent code and security review.
3. **The maintainer approves and merges.** Nothing reaches `main` without that approval. Releases are tagged by the
   maintainer.

## License

By contributing you agree that your contributions are licensed under the MIT License.

## Dependency updates

Renovate runs weekly from `.github/workflows/renovate.yml` and needs a repository secret named `RENOVATE_TOKEN` (a fine-grained personal access token limited to this repository: contents, pull requests and workflows read/write). Without it the workflow fails and nothing else is affected. Pins in `plugins/pavedline/scripts/local-cluster/versions.env` are never automerged.
