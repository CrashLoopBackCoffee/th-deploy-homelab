---
name: container-rightsizing
description: Guidelines for right-sizing container resources using krr in this repository. Use when applying CPU/memory recommendations to a service, interpreting krr output, or creating new resource config models.
license: MIT
---

## Core Rules

- **NEVER** set CPU limits on pods (only CPU requests). See `python-pulumi-patterns` skill.
- **ALWAYS** set memory both as `requests` and `limits` (set both to the same krr-recommended value).
- **ALWAYS** store resource values in the service's `config.py` as a `*ResourcesConfig(LocalBaseModel)` with the krr-recommended values as defaults.
- **NEVER** leave resources unset in production — always apply krr recommendations.

## Step 1: Discover Namespaces Before Running krr

**CRITICAL**: The Pulumi service directory name (e.g., `monitoring`) is **NOT** the Kubernetes
namespace. Always inspect the service code first to find the real namespace(s).

### How to find namespaces

Read the service's Python source files (typically `__main__.py` and files under the service
package directory). Look for:

- `kubernetes.core.v1.Namespace(...)` resource definitions — the `metadata.name` is the namespace.
- Helm chart `Release` or `Chart` objects — their `namespace=` argument or values override.
- Hardcoded namespace strings passed to resource constructors.

Example: in `services/monitoring/__main__.py` you might find:

```python
namespace = kubernetes.core.v1.Namespace("monitoring", metadata={"name": "monitoring"})
# but also:
kubernetes.core.v1.Namespace("kube-state-metrics", metadata={"name": "kube-state-metrics"})
```

This reveals **two** namespaces (`monitoring` and `kube-state-metrics`) that need separate krr runs.

### Build an explicit namespace list

Before calling krr, produce a mapping of sub-service → namespace, e.g.:

| Sub-service / workload | Namespace |
|---|---|
| Prometheus, Grafana, Alloy | `monitoring` |
| kube-state-metrics | `kube-state-metrics` |

Only then proceed to Step 2.

## Step 2: Running krr

Run krr **per namespace** — never assume a single namespace covers all workloads in a service.
Independent namespaces can be queried in parallel (e.g., using sub-agents).

```bash
# Single namespace
krr simple -p https://mimir.tobiash.net/prometheus -n <namespace> -q

# Whole cluster (only use when you need a full overview)
krr simple -p https://mimir.tobiash.net/prometheus -q
```

The `-q` flag suppresses verbose output. krr uses 336 hours of history by default and returns:
- **CPU Requests**: 95th percentile of CPU usage
- **Memory Requests / Limits**: max observed usage + 15% buffer

If the output appears truncated (rows cut off, incomplete table), re-run with CSV output instead:

```bash
krr simple -p https://mimir.tobiash.net/prometheus -n <namespace> -q -f csv
```

CSV output is never truncated and is easier to parse programmatically.

> **NEVER use `--format json` / `-f json`** — JSON output includes full time-series data for every
> container and produces tens of thousands of lines, consuming excessive context and making the
> output impossible to work with. Always use the default table format or `-f csv`.

If krr returns `?` or "No data" for every workload in a namespace, the namespace is almost
certainly **wrong**. Go back to Step 1 and re-inspect the service code.

## Step 3: Interpreting krr Output

The output table has columns:

| Column | Meaning |
|---|---|
| `Name` | Kubernetes Deployment/StatefulSet name (maps to Helm controller key) |
| `Container` | Container name within the pod (usually `main`) |
| `CPU Requests` | Recommended CPU request (e.g. `11m`) |
| `CPU Limits` | **Always ignore** — repo rules forbid CPU limits |
| `Memory Requests` | Recommended memory request (e.g. `835Mi`) |
| `Memory Limits` | Recommended memory limit — set equal to memory request |

Deployment names map to Helm chart component keys:
- `immich-server` → `server`
- `immich-machine-learning` → `machine-learning`
- `immich-valkey` → `valkey`

## Step 4: Applying Resources: Config Model Pattern

Use the shared `utils.model.ResourcesConfig` class — **never** create per-service duplicates.
`ResourcesConfig` has required `cpu` and `memory` fields with **no defaults**, which forces the
values to be explicitly declared in `Pulumi.{stack}.yaml`.

In `config.py`, define a service-level aggregation model and add a required `resources` field:

```python
import utils.model


class ImmichResourcesConfig(utils.model.LocalBaseModel):
    server: utils.model.ResourcesConfig
    machine_learning: utils.model.ResourcesConfig
    valkey: utils.model.ResourcesConfig


class ImmichConfig(utils.model.LocalBaseModel):
    ...
    resources: ImmichResourcesConfig  # required, no default
```

**CRITICAL**: Do not set default values on the config model. Resource values belong in
`Pulumi.{stack}.yaml` so they are explicit, reviewable, and differ per environment if needed.

## Step 5: Applying Resources: Pulumi Stack Config

Because `ResourcesConfig` has no defaults, all values **must** appear in `Pulumi.{stack}.yaml`.
Use krr-recommended values directly — no manual adjustment needed for initial sizing:

```yaml
config:
  immich:config:
    immich:
      resources:
        server:
          cpu: 11m
          memory: 835Mi
        machine-learning:       # note: kebab-case from LocalBaseModel alias_generator
          cpu: 10m
          memory: 6093Mi
        valkey:
          cpu: 10m
          memory: 100Mi
```

For services with a single container, a flat `resources` field is sufficient:

```yaml
config:
  n8n:config:
    n8n:
      resources:
        cpu: 50m
        memory: 512Mi
```

## Step 6: Applying Resources: Helm Values Pattern

In the deployment Python file, inject resources under the controller's container:

```python
'controllers': {
    'main': {
        'containers': {
            'main': {
                'resources': {
                    'requests': {
                        'cpu': component_config.immich.resources.server.cpu,
                        'memory': component_config.immich.resources.server.memory,
                    },
                    'limits': {
                        'memory': component_config.immich.resources.server.memory,
                        # No cpu limit — repo rule
                    },
                },
            },
        },
    },
},
```

For charts that use the `helm-controller-manager` library (like the immich chart), all
components — including bundled ones like `valkey` — follow this same `controllers.main.containers.main.resources` path.

## Step 7: After Applying Changes

1. Regenerate the config schema:
   ```bash
   (cd services/<service> && uv run ../../scripts/generate-config-schema)
   ```
   Or from repo root: `uv run ./scripts/generate-config-schema`

2. Run all checks:
   ```bash
   uv run ./scripts/run-all-checks.sh
   ```

3. Verify with a Pulumi preview before deploying:
   ```bash
   (cd services/<service> && pulumi preview --stack prod)
   ```
