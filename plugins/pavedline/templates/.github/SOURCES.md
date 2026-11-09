# Sources and pins for the CI templates

Checked 2026-11-09. Every pin is exact and at least two weeks old (published on or before 2026-10-26) unless a row says
otherwise; GitHub Actions by full commit SHA (resolved with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>`, annotated
tags dereferenced), images by digest. Re-check before bumping: these are facts at a date. Renovate opens the bumps
(`renovate.json`). The stack-specific CI pins (images, Lighthouse, oasdiff, ZAP, Checkov) are in `docs/architecture/STACK-SOURCES.md`, which step 6 copies
from the stack pack.

| Pin | Version | Published | URL |
|---|---|---|---|
| `actions/checkout` | v7.0.1 `3d3c42e5aac5ba805825da76410c181273ba90b1` | 2026-07-20 | https://github.com/actions/checkout/releases/tag/v7.0.1 |
| `actions/setup-python` | v7.1.0 `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` | 2026-10-22 | https://github.com/actions/setup-python/releases/tag/v7.1.0 |
| `renovatebot/github-action` | v46.3.10 `2804199d260ad00c1fae0e9e842888369391c776` (v46.3.11 and later are under two weeks old) | 2026-10-26 | https://github.com/renovatebot/github-action/releases/tag/v46.3.10 |
| gitleaks image | `ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` | image built 2026-03-21 | https://github.com/gitleaks/gitleaks#docker |
| actionlint (Pavedline's CI and tests) | v1.7.12 | 2026-03-30 | https://github.com/rhysd/actionlint/releases/tag/v1.7.12 |

## Why these choices

- **Renovate token:** `RENOVATE_TOKEN` (a fine-grained personal access token or your own GitHub App's token). `GITHUB_TOKEN`
  is not used because pull requests it opens do not trigger CI (design 11.9). Adding the secret is an ask-before-adding
  step: list it in `SERVICES.md` with its rotation.
- **CODEOWNERS:** `* @OWNER` is a placeholder. GitHub does not fail on an unknown user: "If you specify a user or team
  that doesn't exist or has insufficient access, a code owner will not be assigned"
  (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners,
  2026-11-09). Replace it at step 6.
- **Gates-line check:** `scripts/pr_checks.py` reads the shape of the line in `.github/pull_request_template.md`
  (`Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓`); the template ships it with
  placeholder numbers, so edit them to what really happened.
