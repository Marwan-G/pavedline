# Credits

Pavedline stands on other people's work. This page lists every project it installs, ships, adapts, borrows ideas
from, or uses in its templates and CI, with the author, the licence and how Pavedline uses it. Licences are as
recorded on 2026-11-07; "no licence file detected" means exactly that, and nothing more.

How Pavedline uses a project: **installed** (a plugin dependency, installed from its maker, never copied) ·
**optional** (used only if you have it) · **adapted** (a source rewritten into Pavedline, with credit) · **ideas
only** (read for inspiration, no code or text used) · **used by templates or CI**.

| Project | Author | Licence | How Pavedline uses it |
|---|---|---|---|
| [superpowers](https://github.com/obra/superpowers) | Jesse Vincent | MIT | **Installed** (`plugin.json` dependency): build discipline |
| [mattpocock-skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | **Installed** (`plugin.json` dependency): grilling, to-tickets, retro |
| [product-management](https://github.com/anthropics/knowledge-work-plugins) (from knowledge-work-plugins) | Anthropic | Apache-2.0 | **Installed** (`plugin.json` dependency): competitive brief, research synthesis |
| [@playwright/mcp](https://github.com/microsoft/playwright-mcp) | Microsoft | Apache-2.0 | **Shipped** in the plugin's `.mcp.json`, pinned: competitor research in a browser |
| [crawl4ai](https://github.com/unclecode/crawl4ai) | unclecode | Apache-2.0 (attribution required) | **Optional**: bulk crawling, only if you have it installed |
| [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | nextlevelbuilder | MIT | **Installed from v0.2** (step 7 style reference); not used in v0.1 |
| [impeccable](https://github.com/pbakaus/impeccable) | Paul Bakaus | Apache-2.0 | **Optional**, from v0.2: design critique |
| [Figma plugin and MCP](https://www.figma.com/) | Figma | Figma terms (a Full seat writes to the canvas) | **Installed from v0.2** (step 7); not used in v0.1 |
| Clerk skills | Clerk | no licence file detected | **Later** (stack pack, v0.3): authentication; `doctor` will print the install command |
| [next.js skills](https://github.com/vercel/next.js) | Vercel | MIT | **Later** (stack pack, v0.3) |
| [agent-skills](https://github.com/vercel-labs/agent-skills) | Vercel Labs | no licence file detected | **Later** (stack pack, v0.3) |
| saas-multi-tenant skill | sickn33 | MIT | **Adapted in v0.2** (`multi-tenancy` rules), with credit. Nothing is adapted in v0.1 |
| Supabase Postgres best practices | Supabase | MIT | **Reference** for the v0.2 data rules; nothing copied |
| [ECC](https://github.com/affaan-m/ECC) | affaan-m | MIT | **Ideas only** |
| [spec-kit](https://github.com/github/spec-kit) | GitHub | MIT | **Ideas only** |
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | bmad-code-org | licence not machine-detected | **Ideas only**, cited as inspiration |
| [Graphviz](https://graphviz.org/) | Graphviz authors | see the project (not recorded here) | **Used by templates and CI**: renders every `.dot` diagram to SVG |
| [gitleaks](https://github.com/gitleaks/gitleaks) | gitleaks contributors | MIT | **Used by CI**: secret scan |
| [Renovate](https://github.com/renovatebot/renovate) | Renovate contributors | AGPL-3.0 | **Used by CI** as a tool: dependency update pull requests; no obligation on this repository's code |
| [kind](https://github.com/kubernetes-sigs/kind) | Kubernetes SIGs | Apache-2.0 | **Used by the local cluster scripts and CI** |
| [Helm](https://github.com/helm/helm) | Helm contributors | Apache-2.0 | **Used by the local cluster scripts and CI**: installs the add-ons |
| [Argo CD](https://github.com/argoproj/argo-cd) | Argo Project | Apache-2.0 | **Used by the local cluster scripts and templates**: GitOps |
| [CloudNativePG](https://github.com/cloudnative-pg/cloudnative-pg) | CloudNativePG contributors | Apache-2.0 | **Used by the local cluster scripts and templates**: Postgres on Kubernetes |

Trivy, Checkov and ZAP (all Apache-2.0) are planned for the v0.3 security scanners and are not used in v0.1.

Thank you to every maintainer above. If a row is wrong, or you would like a credit changed or removed, open an
issue.
