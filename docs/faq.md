# FAQ

**Is this waterfall?**
No. Steps 0–7 decide the expensive things once (tenancy, data, authentication, architecture, design). After that,
work ships in small waves of slices, each tested and reviewed. Any earlier step can be reopened with a recorded
decision, and a small fix takes the light path straight to build.

**Does it need the cloud?**
Not until step 12. Everything up to the last step runs on your machine, on a local Kubernetes
cluster. You choose a cloud provider only when the product is ready for production.

**Why local Kubernetes first?**
So that every wave is deployed and checked the way production deploys it (Helm and Argo CD), before any cloud bill
exists. Local cannot prove everything, such as real DNS and TLS; [environments](environments.md) lists what it cannot.

**What does it cost?**
Pavedline is MIT-licensed and free. You pay for what you choose to use: Claude Code (your plan or API), private-repo CI
minutes if your repository is private, and, much later, accounts such as Figma, app stores and a cloud. The
[requirements](../README.md#requirements) table says when each is asked for.

**Does it collect data?**
No. Pavedline collects nothing. Every answer stays in your own repository. Pavedline sends nothing to its author or to any Pavedline service. The only network use is what you install and run yourself, for example npx fetching the Playwright MCP, or marketplace clones.

**Can teams use it?**
Yes. Step 0 asks solo or team. Team mode means parallel sessions in their own worktrees, and approvals move to pull
requests: the spec step opens issues per feature, and the build steps work in branches and worktrees per slice.

**Why these dependencies?**
Pavedline installs excellent existing skills from their makers instead of copying them: superpowers for build
discipline, Matt Pocock's skills for grilling and tickets, and Anthropic's product-management plugin for competitive
research. [CREDITS.md](../CREDITS.md) lists each with its licence. `/pavedline:doctor` tells you what is missing.

**What works today, and what is released?**
Steps 0–12 work on `main`: discover (0–3), design (4–7), deliver on local Kubernetes (8–11), then the integration
wave, step 12 and the Grow loop. The latest tagged release is still v0.1. Details in the [roadmap](../README.md#roadmap).

**Will it ever run commands on my real cluster?**
A hook blocks mutating `kubectl`, `helm` and `argocd` commands unless the context is a local `kind-pavedline-*`
cluster. It also blocks reading `.env` files and writing secrets into files.
