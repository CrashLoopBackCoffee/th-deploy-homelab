---
name: pulumi-operations
description: Guidelines for running Pulumi commands safely in this repository. Use when deploying services, running pulumi up or preview, managing stacks, or renaming Pulumi resources.
license: MIT
---

## Safety Rules (non-negotiable)

1. **ALWAYS** run `pulumi preview --diff` before `pulumi up` — check the diff for unexpected changes.
2. **ALWAYS** use `--non-interactive` flag with `pulumi up` and `pulumi preview` to prevent interactive prompts from breaking terminal integration.
3. **ALWAYS** use a subshell when changing into a service directory — see the Shell Safety section below.

## Shell Safety

Never use `cd foo && command` — it permanently changes the working directory of the
shell session. Always isolate directory changes to a subshell:

```bash
# CORRECT: directory change is scoped to the subshell
(cd services/n8n && pulumi preview -s prod --diff --non-interactive)

# WRONG: permanently changes the shell's working directory
cd services/n8n && pulumi preview -s prod --diff --non-interactive
```

## Common Pulumi Commands

```bash
# Preview changes (ALWAYS run this first)
(cd services/{service-name} && pulumi preview -s {stack-name} --diff --non-interactive)

# Deploy (only after reviewing preview)
(cd services/{service-name} && pulumi up -s {stack-name} --non-interactive --skip-preview)

# List available stacks for a service
(cd services/{service-name} && pulumi stack ls)

# Show current stack configuration
(cd services/{service-name} && pulumi config --stack {stack-name})
```

## Stack Names

| Stack | Purpose |
|---|---|
| `prod` | Primary homelab environment for most services |
| `dev` | Legacy environment (`monitoring`, `proxmox`, `s3`) |
| `test` | Experimental, especially for `kubernetes` changes |

## Renaming a Resource

When renaming a Pulumi resource, always add an alias to preserve the existing state
and prevent unnecessary destruction and recreation:

```python
k8s.core.v1.Namespace(
    'new-name',
    metadata={'name': 'my-namespace'},
    opts=p.ResourceOptions(
        provider=k8s_provider,
        aliases=[p.Alias(name='old-name')],
    ),
)
```

Remove the alias in a follow-up commit once the rename has been applied successfully.
