---
name: container-image-management
description: Guidelines for managing container image versions, renovate annotations, and config model patterns in this repository. Use when adding new container images, updating existing image versions, or configuring any container-based service.
license: MIT
---

## Core Rules

- **NEVER** hardcode image tags in Python code.
- **ALWAYS** include image versions in the service's configuration model (`config.py`).
- **ALWAYS** verify version numbers against actual upstream releases before adding them.
- **PREFER official container images** over runtime tool downloads.

## Version Field in config.py

Add a `version` field to the relevant Pydantic model in the service's `config.py`:

```python
class N8nConfig(utils.model.LocalBaseModel):
    version: str          # populated from Pulumi.{stack}.yaml
    hostname: str
```

Reference it in Python code using string interpolation — never hard-code the tag:

```python
'image': f'n8nio/n8n:{component_config.n8n.version}',
```

## Renovate Annotations in Pulumi.{stack}.yaml

Add a `renovate` comment **immediately above** every version field so Renovate can
auto-update it. The comment must be on the line directly preceding the field.

### GitHub Releases (most common)

```yaml
# renovate: datasource=github-releases packageName=n8n-io/n8n versioning=semver
version: 1.108.1
```

### GitHub Releases with custom version extraction

Some projects prefix tags (e.g. `mimir-3.0.3`); use `extractVersion` to strip the prefix:

```yaml
# renovate: datasource=github-releases packageName=grafana/mimir extractVersion=^mimir-(?<version>.*)$ versioning=semver
version: 3.0.3
```

### Helm chart versions

Prefer `github-releases` over `helm` when the chart's GitHub repository publishes
tagged releases (use `extractVersion` to strip the chart-name prefix from the tag):

```yaml
# renovate: datasource=github-releases packageName=prometheus-community/helm-charts extractVersion=^kube-state-metrics-(?<version>.*)$ versioning=semver
version: 7.1.0
```

```yaml
# renovate: datasource=github-releases packageName=immich-app/immich-charts extractVersion=^immich-(?<version>.*)$ versioning=semver
chart-version: "0.10.0"
```

Fall back to `datasource=helm` only when no matching GitHub releases exist:

```yaml
# renovate: datasource=helm packageName=fairwinds-stable/goldilocks
version: 10.1.0
```

### End-of-life / major release tracking

```yaml
# renovate: datasource=endoflife-date packageName=postgresql extractVersion=^(?<version>\d+) versioning=loose
version: 18
```

### Loose versioning (no semver guarantee)

```yaml
# renovate: datasource=github-releases packageName=prometheus/node_exporter versioning=loose
version: 1.10.2
```

## Config File Placement

The version field lives in `Pulumi.{stack}.yaml` under the service's config namespace:

```yaml
config:
  n8n:config:
    n8n:
      # renovate: datasource=github-releases packageName=n8n-io/n8n versioning=semver
      version: 1.108.1
```

The `{stack}` is the Pulumi stack name (e.g. `prod`, `dev`, `test`).
