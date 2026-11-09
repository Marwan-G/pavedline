# Sources for the deploy skill (checked 2026-11-09)

Facts at a date, not rules; re-check before relying on them.

| Fact | Value | Source | Date |
|---|---|---|---|
| A manual Argo CD sync operation carries its own options | `CreateNamespace=true` is documented as a `syncOptions` entry of the Application; an `operation.sync` patch by hand did not apply it (observed on the real kind cluster, Task 6: `namespace web not found`), so the script puts it in the operation. | https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/ (page read 2026-11-09) and the Task 6 cluster run | 2026-11-09 |
| PreSync hooks | The API chart's migration Job carries `argocd.argoproj.io/hook: PreSync` and `BeforeHookCreation`; a failed hook fails the sync and a retried sync recreates the Job. Observed on the real cluster in Tasks 5b and 6; the vendor page https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/ could not be read as text on 2026-11-09, so the behaviour is recorded from the runs, not the page. | the cluster runs | 2026-11-09 |
| Skip-CI markers GitHub honours | `[skip ci]`, `[ci skip]`, `[no ci]`, `[skip actions]`, `[actions skip]` in the commit message of a push or the HEAD commit of a pull request, or a `skip-checks: true` / `skip-checks:true` trailer; applies to `push` and `pull_request` events (read 2026-11-09). | https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs | 2026-11-09 |
| Other markers | `***NO_CI***` is not in GitHub's list; some other CI systems honour it. It is checked as well out of caution (not verified against any vendor page). `skip-checks: true` is GitHub's trailer form and is checked too. | https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs | 2026-11-09 |
| `gh run list --commit` | lists workflow runs for a commit sha; `--json name,status,conclusion` | https://cli.github.com/manual/gh_run_list | 2026-11-09 |
| `gh api` | calls any REST endpoint; `{owner}/{repo}` placeholders resolve from the current repository | https://cli.github.com/manual/gh_api | 2026-11-09 |
| Local ports and hosts | host port 8080 reaches the Envoy Gateway NodePort 30080; `*.localtest.me` resolves to 127.0.0.1 | `local-cluster` skill; checked 2026-11-09 | 2026-11-09 |
