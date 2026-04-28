# Agent Instructions

Homelab IaC project: **Python + Pulumi + UV**, deployed on Proxmox/MicroK8s with Cloudflare DNS. Each service lives in its own workspace under `services/`. Shared utilities in `utils/`.

## Rules

1. **Shell**: NEVER `cd foo && command` — always use `(cd foo && command)` in a subshell.
2. **Linting**: ALWAYS run `uv run ./scripts/run-all-checks.sh` BEFORE committing. Run linters BEFORE manually fixing code (many auto-fix).
3. **Git**: Feature branches only. Never commit directly to `main`.

## Skills

Delegated to topic-specific skills — always consult before making changes:
- **Pulumi operations**: `pulumi-operations` (safety, deployment, stack management, resource renames)
- **Python code style**: `python-pulumi-patterns` (imports, types, config models, K8s typed-dicts, CPU limits)
- **Container images**: `container-image-management` (versions, renovate annotations)
- **Helm charts**: `helm-chart-management` (Chart vs Release, hooks)

## Stacks

- `prod`: primary environment
- `dev`: legacy (`monitoring`, `proxmox`, `s3`)
- `test`: experimental (mainly `kubernetes`)
