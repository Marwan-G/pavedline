# Contributing to Pavedline

Thanks for your interest. Pavedline is a Claude Code plugin marketplace; contributions are welcome.

## Ground rules

- Python code uses the standard library only and targets Python 3.10+.
- Run the tests with `python3 -m unittest discover -s tests -t .`.
- Validate manifests with `claude plugin validate . --strict` and
  `claude plugin validate plugins/pavedline --strict`.
- Keep changes focused: one concern per pull request, with tests for new behavior.
- Do not commit secrets, local paths, or identifiers that belong to a private project.

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
