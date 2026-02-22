---
name: python-pulumi-patterns
description: Python code style and patterns for this repository. Use when writing or reviewing any Python code, including Pulumi components, config models, and Kubernetes resource definitions.
license: MIT
---

## Import Style

Group imports in this order, separated by blank lines:

1. Standard library (`import json`, `import pathlib`)
2. External packages (`import pulumi as p`, `import pulumi_kubernetes as k8s`)
3. Internal/project imports (`from n8n.config import ComponentConfig`)

Use `from ... import ...` only for internal/project imports. Use `import ...` for everything else.

### Canonical Abbreviations

Only these abbreviations are permitted:

```python
import typing as t
import pulumi as p
import pulumi_kubernetes as k8s
import collections.abc as c
```

All other packages are imported by full name: `import pulumi_cloudflare`, `import pathlib`.

### Example

```python
import json

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig
```

## Type Annotations

Use modern Python union syntax — not `Optional`:

```python
# CORRECT
version: str | None = None
items: list[str] | None = None

# WRONG
version: Optional[str] = None
```

## Configuration Models with LocalBaseModel

All service config models extend `utils.model.LocalBaseModel`, which:

- Auto-generates kebab-case aliases (`snake_case` → `kebab-case`) for Pulumi YAML keys
- Sets `extra = 'forbid'` to catch unknown/misspelled config keys
- Never requires manual `Field(alias=...)` — aliases are generated automatically

### Pattern

```python
import utils.model


class N8nConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    webhook_url: str = ''          # alias in YAML: webhook-url


class ComponentConfig(utils.model.LocalBaseModel):
    n8n: N8nConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig
```

- `StackConfig.alias_generator` maps to Pulumi's namespaced key format: `n8n:config`
- Do not add pydantic `Field(alias=...)` — `LocalBaseModel` handles aliasing automatically

## Kubernetes Resources: TypedDict Notation

Prefer plain dict notation over `Args` classes for Kubernetes resources. It is more
concise and aligns with the project's Python idioms.

```python
# CORRECT: plain dict notation
namespace = k8s.core.v1.Namespace(
    'n8n',
    metadata={
        'name': 'n8n',
    },
    opts=k8s_opts,
)

# WRONG: Args class notation
namespace = k8s.core.v1.Namespace(
    'n8n',
    metadata=k8s.meta.v1.ObjectMetaArgs(name='n8n'),
    opts=k8s_opts,
)
```

Use dict notation for all nested structures too (specs, containers, volumes, probes, etc.).

## Kubernetes: CPU Limits

**Never** set CPU limits on pods. Set only CPU requests and memory limits/requests:

```python
'resources': {
    'requests': {
        'memory': '512Mi',
        'cpu': '250m',
    },
    'limits': {
        'memory': '1Gi',
        # no cpu limit
    },
},
```

## General Patterns

- Use type hints consistently and follow PEP 8.
- Prefer composition over inheritance for Pulumi `ComponentResource` classes.
- Use `LocalBaseModel` (not raw dataclasses) for structured config data.
- Keep `pyproject.toml` dependency lists sorted alphabetically.
