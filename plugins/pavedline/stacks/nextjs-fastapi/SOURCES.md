# Sources and pins for the JavaScript side of the `nextjs-fastapi` pack

Checked 2026-11-09. Every pin is exact (no `^` or `~`) and at least two weeks old (published on or before 2026-10-26),
except where a row says otherwise. `pnpm-workspace.yaml` sets `minimumReleaseAge: 20160` (minutes), so pnpm refuses
any transitive package younger than 14 days when it writes `pnpm-lock.yaml` (the install prints "Lockfile passes
supply-chain policies"; vite 8.3.5, pulled in by vitest, was checked by hand). These are facts at a date: re-check
before bumping. The Python side is in `skills/fastapi-service/references/sources.md`.

## npm packages (package.json, exact)

| Package | Pin | Published | URL |
|---|---|---|---|
| `next` | `16.4.3` | 2026-10-23 | https://www.npmjs.com/package/next/v/16.4.3 |
| `@next/mdx` | `16.4.3` | 2026-10-23 | https://www.npmjs.com/package/@next/mdx/v/16.4.3 |
| `react` | `19.3.1` | 2026-10-14 | https://www.npmjs.com/package/react/v/19.3.1 |
| `react-dom` | `19.3.1` | 2026-10-14 | https://www.npmjs.com/package/react-dom/v/19.3.1 |
| `server-only` | `0.0.1` | 2022-09-03 | https://www.npmjs.com/package/server-only/v/0.0.1 |
| `@mdx-js/loader` | `3.1.1` | 2025-08-29 | https://www.npmjs.com/package/@mdx-js/loader/v/3.1.1 |
| `@mdx-js/react` | `3.1.1` | 2025-08-29 | https://www.npmjs.com/package/@mdx-js/react/v/3.1.1 |
| `@types/mdx` | `2.0.14` | 2026-06-06 | https://www.npmjs.com/package/@types/mdx/v/2.0.14 |
| `@types/node` | `26.6.5` | 2026-10-09 | https://www.npmjs.com/package/@types/node/v/26.6.5 |
| `@types/react` | `19.3.0` | 2026-09-09 | https://www.npmjs.com/package/@types/react/v/19.3.0 |
| `@types/react-dom` | `19.3.0` | 2026-09-09 | https://www.npmjs.com/package/@types/react-dom/v/19.3.0 |
| `typescript` | `5.9.3` | 2025-09-30 | https://www.npmjs.com/package/typescript/v/5.9.3 |
| `@biomejs/biome` | `2.6.3` | 2026-10-24 | https://www.npmjs.com/package/@biomejs/biome/v/2.6.3 |
| `vitest` | `5.0.5` | 2026-10-15 | https://www.npmjs.com/package/vitest/v/5.0.5 |
| `@playwright/test` | `1.64.1` | 2026-10-14 | https://www.npmjs.com/package/@playwright/test/v/1.64.1 |
| `@axe-core/playwright` | `4.14.0` | 2026-10-15 | https://www.npmjs.com/package/@axe-core/playwright/v/4.14.0 |
| `openapi-typescript` | `7.13.0` | 2026-02-11 | https://www.npmjs.com/package/openapi-typescript/v/7.13.0 |
| `openapi-fetch` | `0.17.0` | 2026-02-11 | https://www.npmjs.com/package/openapi-fetch/v/0.17.0 |
| `pnpm` | `11.28.8` | 2026-10-22 | https://www.npmjs.com/package/pnpm/v/11.28.8 |

Why these:
- **Next.js 16.4.3** (16.4.5 was latest on 2026-11-09 but is under two weeks old). The spec asks for 16.3 or later.
  From 16.x the middleware convention is `proxy.ts` (the site uses it to set `X-Robots-Tag` from the runtime environment).
- **TypeScript 5.9.3, not 6.0.3 or 7.0.2:** `openapi-typescript@7.13.0` declares `typescript ^5` as a peer, and the
  install reported an unmet peer with 6.0.3. 5.9.3 is the newest release that satisfies every peer; revisit when
  openapi-typescript 8 lands or declares 6.
- **openapi-typescript 7.13.0 with openapi-fetch 0.17.0** (generator and client): MIT, maintained together, zero
  runtime code beyond `fetch`, types come straight from the OpenAPI document, and the output is deterministic so the
  `check` script can diff it. Both are the latest releases (none since 2026-02-11).
- **vitest 5.0.5** (latest 5.1.0 is newer than the cutoff; 4.1.12 is the last 4.x). Node-environment unit tests only;
  there are no component tests, so no jsdom or Testing Library.
- **@playwright/test 1.64.1 and @axe-core/playwright 4.14.0:** the browser test and the WCAG 2.2 AA check. The browser
  binary is not a pin of ours: `pnpm exec playwright install chromium` installs the build that matches 1.64.1.
- **pnpm 11.28.8** (12.16.0 is exactly 14 days old on 2026-11-09, so it is left out). Node 25 and later do not
  ship corepack, so the Dockerfiles run `npm install --global pnpm@11.28.8` and local use is
  `npx --yes pnpm@11.28.8 <command>` when pnpm is not installed.
- **@biomejs/biome 2.6.3:** one formatter and linter for TS, JS and JSON (`biome ci`); the schema URL in `biome.json`
  carries the same version.
- **CSP `'unsafe-inline'`** (web and site): deliberate, because Next.js inlines its bootstrap script and a nonce forces per-request rendering; a product with user-generated content moves to nonces. No `'unsafe-eval'`.
- `server-only 0.0.1` is the latest release (2022); `@mdx-js/*` 3.1.1 are the latest releases.

## Node and the images

| Pin | Value | URL / date |
|---|---|---|
| Node | `26.12.1` (`.node-version`). Node 26 is the Active LTS line since 2026-10-28 (Node 24 is in maintenance, Node 22 until 2027-04-30). 26.12.1 was published 2026-10-21; 26.13.0, the first release tagged LTS, came on 2026-10-28 (12 days old, under the two-week rule). | https://github.com/nodejs/Release/blob/main/schedule.json (2026-11-09), https://nodejs.org/dist/index.json |
| Image | `node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797` (Docker Hub index digest; amd64 pushed 2026-10-21, arm64 2026-10-22) | https://hub.docker.com/_/node (2026-11-09) |

## Agent skills enabled by the pack (`pack.yaml` `skills:`)

Names checked on GitHub on 2026-11-09 (contents API, `skills/` folder of each repository). Install with the skills
CLI: `npx skills add vercel/next.js --skill <name>` or `npx skills add vercel-labs/agent-skills --skill <name>` (CLI usage:
https://github.com/vercel-labs/skills).

| Source | Skills listed in `pack.yaml` | URL |
|---|---|---|
| `vercel/next.js` (`skills/`) | `next-dev-loop`, `next-bundle-optimizer`, `next-cache-components-adoption`, `next-cache-components-optimizer`, `next-partial-prefetching-adoption`, `next-partial-prefetching-optimizer` | https://github.com/vercel/next.js/tree/canary/skills |
| `vercel-labs/agent-skills` (`skills/`) | `react-best-practices`, `composition-patterns`, `web-design-guidelines`, `react-view-transitions`, `react-native-skills` (mobile; name checked 2026-11-09) | https://github.com/vercel-labs/agent-skills/tree/main/skills |

Present in the same repositories and left out on purpose: `deploy-to-vercel`, `vercel-cli-with-tokens` and
`vercel-optimize` (deploys go through GitOps, never a vendor CLI).

## Mobile (`apps/mobile`)

Checked 2026-11-09; full table with URLs and dates, the ESLint-10 note for the a11y plugin and the build requirements:
`skills/mobile-build/references/sources.md`. Exact pins in `apps/mobile/package.json`:

| Package | Pin | Published |
|---|---|---|
| `expo` | `58.0.19` (SDK 58; 58.0.20 and later are under two weeks) | 2026-10-23 |
| `react` / `react-native` | `19.3.0` / `0.88.0` (Expo's version table for 58.0.19) | 2026-09-09 / 2026-10-15 |
| `expo-constants`, `expo-status-bar` | `58.0.13`, `58.0.4` | 2026-10-21 |
| `jest-expo`, `@react-native/jest-preset`, `test-renderer` | `58.0.12`, `0.88.0`, `1.3.0` | 2026-10-21, 2026-10-15, 2026-09-17 |
| `@testing-library/react-native`, `jest`, `@types/jest` | `14.1.0`, `30.5.2`, `30.0.0` | 2026-10-08, 2026-09-18, 2025-06-16 |
| `eslint`, `typescript-eslint`, `@eslint/js` | `10.13.0`, `8.72.0`, `9.39.5` | 2026-10-16, 2026-10-19, 2026-07-10 |
| `eslint-plugin-react-native-a11y` | `3.5.1` (unmaintained since 2024, peer ESLint 8, works on ESLint 10 (tested); fallback fork `@volksverpetzer/eslint-plugin-react-native-a11y` 3.6.0, 2026-09-24) | 2024-11-04 |

`pnpm-workspace.yaml` gained `allowBuilds` (`@parcel/watcher`, `unrs-resolver`: install scripts stay off).

## CI (`files/.github/workflows/`)

Checked 2026-11-09. Pins at least two weeks old (published on or before 2026-10-26); Actions by full SHA (resolved with
`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`, annotated tags dereferenced), images by digest, release binaries by
sha256. The stack-neutral pins (checkout, setup-python, Renovate, gitleaks) are in `templates/.github/SOURCES.md`.

| Pin | Version | Published | URL |
|---|---|---|---|
| `actions/setup-node` | v7.1.0 `949feb2413d6458794dcd2491c4babbbce0c15c1` | 2026-10-08 | https://github.com/actions/setup-node/releases/tag/v7.1.0 |
| `actions/setup-java` | v6.1.0 `b843ebf9b913146b38da2eaa7aeddf76074ae1ad` (v6.2.0 is 2026-11-04, too young) | 2026-10-14 | https://github.com/actions/setup-java/releases/tag/v6.1.0 |
| `actions/upload-artifact` | v7.0.2 `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | 2026-10-07 | https://github.com/actions/upload-artifact/releases/tag/v7.0.2 |
| `astral-sh/setup-uv` | v10.3.2 `07a047e608db84b3d8c06cd9a7c7dcc9c355c18e` (installs uv 0.13.5, the pack's pin) | 2026-10-22 | https://github.com/astral-sh/setup-uv/releases/tag/v10.3.2 |
| Semgrep image | `semgrep/semgrep:1.182.0@sha256:4a34048c04fef049f71665047f074cffb00cc3d89482f965a5cd151d589237af` (linux/amd64 and arm64; v1.183.0 and v1.184.0 are too young) | 2026-10-20 | https://github.com/semgrep/semgrep/releases/tag/v1.182.0 |
| Trivy image | `ghcr.io/aquasecurity/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c` (linux/amd64 and arm64; v0.76.2 of 2026-11-05 is too young) | 2026-10-21 | https://github.com/aquasecurity/trivy/releases/tag/v0.76.1 |
| OWASP ZAP image | `ghcr.io/zaproxy/zaproxy:2.16.1@sha256:7840969c7c9fead565bf9734b12f49f6886db90b1d35b1f74d79710bbd081dab` (linux/amd64 and arm64; the 2.17.0 tag was rebuilt 2026-11-03, under 14 days, so it is not used) | image built 2025-12-12 | https://github.com/zaproxy/zaproxy/pkgs/container/zaproxy |
| oasdiff | v1.34.1 release binary `oasdiff_1.34.1_linux_amd64.tar.gz`, sha256 `75775f65b0adebd26a8e013af51a799342dfdc6262d89efa9e3b7bdf89657d90` from the release's `checksums.txt` (v1.35.0 of 2026-10-28 is too young) | 2026-10-21 | https://github.com/oasdiff/oasdiff/releases/tag/v1.34.1 |
| `@lhci/cli` | 0.15.1 (0.16.0 is 2026-11-02, too young) | 2025-06-25 | https://www.npmjs.com/package/@lhci/cli/v/0.15.1 |
| Checkov image | `bridgecrew/checkov:3.3.30@sha256:4b65e89f1fde292249fc0aa0d0db43302c036dfe39f7370b2d3517571082b894` (OCI index digest; amd64 and arm64; entrypoint `checkov`; the pip package floats its dependencies, so CI uses the image; the chart tests still use `uvx checkov==3.3.30`) | 2026-10-20 | https://hub.docker.com/r/bridgecrew/checkov/tags |
| Postgres service image | `postgres:16.14@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b` (OCI index digest; same major as the CloudNativePG image, 16.15; 16.15's official image was rebuilt 2026-11-05, under 14 days, so it is not used) | image built 2026-08-05 | https://hub.docker.com/v2/repositories/library/postgres/tags/16.14 |
| helm | v4.3.1 linux-amd64 sha256 `0403a88a...fe54b` (from `helm-v4.3.1-linux-amd64.tar.gz.sha256sum`); arm64 as in Pavedline's own CI | | https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz.sha256sum |
| kind | v0.33.0 (arm64 sha256 as in Pavedline's own CI) | | https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0 |
| actionlint (Pavedline's CI, not the product's) | v1.7.12 linux-amd64 sha256 `8aca8db9...3d8`, from `actionlint_1.7.12_checksums.txt` | 2026-03-30 | https://github.com/rhysd/actionlint/releases/tag/v1.7.12 |

Why these choices:
- **Trivy runs from its official image, not `aquasecurity/trivy-action`.** Security history (checked 2026-11-09): on
  2026-03-19 a threat actor with compromised credentials published a malicious Trivy v0.69.4, force-pushed 76 of the 77
  version tags of `aquasecurity/trivy-action` to credential-stealing code and replaced all 7 tags of
  `aquasecurity/setup-trivy`; on 2026-03-22 malicious v0.69.5 and v0.69.6 images were published on Docker Hub (advisory
  GHSA-69fq-xp46-6x23: https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23). The advisory says images
  referenced by digest were not affected, and a mutable tag is exactly what a force-push rewrites, so Pavedline pins
  the image by digest (and Actions by SHA) and uses no third-party wrapper. Three more advisories were published between
  2026-06-04 and 2026-06-30 (Helm-chart tar bomb, path traversal in downloaded artifacts, path traversal in the plugin
  manager): re-check the advisory list before bumping (`gh api repos/aquasecurity/trivy/security-advisories`).
- **Semgrep:** `semgrep scan --config p/default --metrics=off --error`. `p/default` is the registry ruleset
  (https://semgrep.dev/p/default answers 200, 2026-11-09; the CI docs show `--config p/default` as an example,
  https://docs.semgrep.dev/semgrep-ci/running-semgrep-ci-without-semgrep-cloud-platform). `--config auto` is not used. The
  docs page does not mention `--metrics=off` or `--error`; both are CLI flags (https://semgrep.dev/docs/cli-reference).
  Not yet proven here: no scan has run, so the first CI run decides whether the findings need a `.semgrepignore`.
- **Lighthouse budgets (starter, `apps/site/lighthouserc.json`):** accessibility >= 0.9 and SEO >= 0.9, error level.
  They are thresholds to raise, not measured values (no run yet; the first CI run is the measurement). The cluster run
  drops SEO because the local site is `noindex` on purpose.
- **ZAP baseline policy:** `-I` (warnings do not fail the run, a FAIL-level alert does). Reports are uploaded as the
  `zap-reports` artifact. Tighten with a rules file (`-c`) after the first run shows what the starter app triggers.
- **GitHub-hosted runner cost (Ruling 8, re-checked 2026-11-09):** standard runners are free and unlimited in public
  repositories (https://docs.github.com/en/actions/reference/runners/github-hosted-runners). On private repositories they are billed per
  minute: Linux 2-core arm64 $0.005, macOS 3 or 4-core $0.062
  (https://docs.github.com/en/billing/reference/actions-runner-pricing). `ci-mobile.yml` therefore builds the iOS app only on its path filter
  and weekly.
- **`macos-26`** is the macOS arm64 label named in the same runners page (Task 7 evidence, 2026-11-09).

### Image build dates (rule: an image is pinned only if it was BUILT at least 14 days before the pin date, 2026-11-09)

Read from each image's config `created` field (registry API, arm64 manifest, 2026-11-09); a tag can be rebuilt, so the
release date alone proves nothing.

| Image | Built |
|---|---|
| `semgrep/semgrep:1.182.0` | 2026-10-20 |
| `ghcr.io/aquasecurity/trivy:0.76.1` | 2026-10-21 |
| `ghcr.io/zaproxy/zaproxy:2.16.1` | 2025-12-12 |
| `bridgecrew/checkov:3.3.30` | 2026-10-20 |
| `postgres:16.14` | 2026-08-05 |
| `ghcr.io/gitleaks/gitleaks:v8.30.1` | 2026-03-21 |

Carry for Task 10: `apply_stack` copies this file into the product as `docs/architecture/STACK-SOURCES.md`; the workflow
comments point there.
