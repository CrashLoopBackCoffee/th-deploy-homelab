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

## Running krr

```bash
# Single namespace
krr simple -p https://mimir.tobiash.net/prometheus -n <namespace> -q

# Whole cluster
krr simple -p https://mimir.tobiash.net/prometheus -q
```

The `-q` flag suppresses verbose output. krr uses 336 hours of history by default and returns:
- **CPU Requests**: 95th percentile of CPU usage
- **Memory Requests / Limits**: max observed usage + 15% buffer

## Interpreting krr Output

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

## Applying Resources: Config Model Pattern

Add nested `*ResourcesConfig` classes to the service's `config.py`. Each class holds the krr-recommended values as defaults:

```python
class ServerResourcesConfig(utils.model.LocalBaseModel):
    cpu: str = '11m'
    memory: str = '835Mi'


class MachineLearningResourcesConfig(utils.model.LocalBaseModel):
    cpu: str = '10m'
    memory: str = '6093Mi'


class ValkeyResourcesConfig(utils.model.LocalBaseModel):
    cpu: str = '10m'
    memory: str = '100Mi'


class ImmichResourcesConfig(utils.model.LocalBaseModel):
    server: ServerResourcesConfig = ServerResourcesConfig()
    machine_learning: MachineLearningResourcesConfig = MachineLearningResourcesConfig()
    valkey: ValkeyResourcesConfig = ValkeyResourcesConfig()


class ImmichConfig(utils.model.LocalBaseModel):
    ...
    resources: ImmichResourcesConfig = ImmichResourcesConfig()
```

Defaults in the config class mean the values work without any `Pulumi.{stack}.yaml` entries. Override in YAML only when a specific stack needs different tuning:

```yaml
config:
  immich:config:
    immich:
      resources:
        server:
          memory: 1Gi
```

## Applying Resources: Helm Values Pattern

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

## After Applying Changes

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
