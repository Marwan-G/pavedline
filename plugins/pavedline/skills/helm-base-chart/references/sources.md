# Sources and pins for helm-base-chart

Checked 2026-11-09.

| Fact | Value | Source |
|---|---|---|
| Helm tested | v4.3.1 (`helm version`, 2026-11-09). Library charts, `file://` dependencies and JSON-schema validation of values all work in Helm 4; a library chart's own `values.schema.json` would validate the wrong values, so the schema ships as `app-values.schema.json` and each app chart copies it. | https://helm.sh/docs/ , https://github.com/helm/helm/releases |
| Gateway API (pinned) | v1.6.3, released 2026-10-06 (latest at least two weeks old; v1.7.0 was released 2026-10-29, under two weeks). The chart uses `gateway.networking.k8s.io/v1` `HTTPRoute`. | https://github.com/kubernetes-sigs/gateway-api/releases |
| Checkov (pinned) | `checkov==3.3.30` (run with `uvx`), uploaded 2026-10-20 (latest at least two weeks old; 3.4.0 to 3.4.3 are from 2026-10-28 to 2026-11-02). Run on rendered output in CI, not in this task. | https://pypi.org/project/checkov/3.3.30/ |
| ingress-nginx | Retired by Kubernetes (no security fixes after March 2026); hence Gateway API. | spec §11.6 |
| Argo CD hooks | `argocd.argoproj.io/hook: PreSync` and `hook-delete-policy: BeforeHookCreation` | https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/ |
