---
name: helm-chart-management
description: Guidelines for deploying Helm charts with Pulumi in this repository. Use when adding a new Helm chart, or deciding between k8s.helm.v4.Chart and k8s.helm.v3.Release.
license: MIT
---

## Chart vs Release: Decision Rule

**Default: use `k8s.helm.v4.Chart`** — it creates individual Pulumi resources for each
Helm resource, enabling fine-grained dependency tracking, output references, and
`depends_on` targeting.

**Exception: use `k8s.helm.v3.Release`** when the chart uses Helm hooks (`pre-install`,
`post-install`, `pre-delete`, `post-delete`, etc.). Hooks run outside Pulumi's
resource graph; `Chart` cannot handle them correctly.

## How to Check for Hooks Before Choosing

```bash
# Render the chart locally and grep for hook annotations
helm template <release-name> <repo>/<chart> --version <version> | grep 'helm.sh/hook'
```

If that grep returns any results, use `v3.Release`. Otherwise use `v4.Chart`.

Common hook use cases: database migration jobs, CRD installation jobs, cleanup jobs.

## k8s.helm.v4.Chart (preferred)

```python
import pulumi as p
import pulumi_kubernetes as k8s

k8s.helm.v4.Chart(
    'kube-state-metrics',
    chart='kube-state-metrics',
    version=component_config.kube_state_metrics.version,
    namespace=namespace.metadata.name,
    repository_opts={'repo': 'https://prometheus-community.github.io/helm-charts'},
    opts=p.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
)
```

When you need to reference an individual resource from the chart (e.g. a Service):

```python
chart = k8s.helm.v4.Chart(
    'traefik',
    chart='traefik',
    namespace=namespace.metadata.name,
    version=f'v{component_config.traefik.version}',
    repository_opts={'repo': 'https://traefik.github.io/charts'},
    values={...},
    opts=k8s_opts,
)

traefik_service = chart.resources.apply(
    lambda resources: [r for r in resources if isinstance(r, k8s.core.v1.Service)][0]
)
```

## k8s.helm.v3.Release (hooks only)

```python
import pulumi as p
import pulumi_kubernetes as k8s

chart = k8s.helm.v3.Release(
    'cert-manager',
    chart='cert-manager',
    version=component_config.cert_manager.version,
    namespace=namespace.metadata.name,
    repository_opts={'repo': 'https://charts.jetstack.io'},
    values={
        'crds': {
            'enabled': True,
        },
    },
    opts=k8s_opts,
)
```

Note: `v3.Release` is an opaque resource — Pulumi has no visibility into the child
resources it creates, and you cannot reference them directly.

## Helm Chart Version in Config

Chart versions follow the same renovate annotation pattern as container images:

```yaml
# renovate: datasource=helm packageName=prometheus-community/kube-state-metrics
version: 7.1.0
```

See the `container-image-management` skill for the full set of renovate annotation patterns.
