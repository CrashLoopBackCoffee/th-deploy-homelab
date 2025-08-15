# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# CRITICAL: Run all checks before committing (includes linting, type checking, pre-commit hooks)
uv run ./scripts/run-all-checks.sh

# Generate config schemas for VS Code YAML validation
uv run ./scripts/generate-config-schema

# Deploy services (use subshells to avoid changing working directory)
# ALWAYS preview first to check for unexpected changes
(cd services/{service-name} && pulumi preview -s {stack-name} --diff --non-interactive)
(cd services/{service-name} && pulumi up --stack {stack-name} --non-interactive --skip-preview)

# List available stacks for a service
(cd services/{service-name} && pulumi stack ls)
```

## Project Architecture

This is a homelab infrastructure-as-code project using **Pulumi with Python** to manage services across multiple environments. Key architectural patterns:

### Service Structure
- **Microservices architecture**: Each service in `services/` is an independent Pulumi workspace
- **Shared utilities**: Common code in `utils/src/utils/` workspace
- **Stack-based environments**: `dev`, `test`, `prod` stacks with service-specific usage patterns

### Core Services
- `kubernetes/`: MicroK8s cluster management (Proxmox VMs with CSI, MetalLB, Traefik, cert-manager)
- `monitoring/`: Observability stack (Prometheus, Grafana, Alloy)
- `proxmox/`: VM provisioning (Pulumi) + configuration (Ansible playbooks)
- `ingress/`: Cloudflare tunnels and ingress management
- `paperless/`: Document management with dual backup system (Google Drive + IDrive E2)
- `iot/`: MQTT broker, Z-Wave controller, metrics collection
- `obsidian/`, `unifi/`, `s3/`: Knowledge management, network management, object storage

### Configuration Management
- **Type-safe configs**: Each service has `config.py` with Pydantic models
- **Pattern**: `ComponentConfig.model_validate(p.Config().get_object('config'))`
- **Stack configs**: `Pulumi.{stack}.yaml` files with schema validation
- **Secrets**: Pulumi secrets with `.value` accessor for sensitive data

### Container Image Management
- **NEVER** hardcode image tags in Python code
- **ALWAYS** include versions in config models with renovate comments:
```yaml
# renovate: datasource=github-releases packageName=owner/repo versioning=semver
service-version: "1.0.0"
```
- Use config values: `f'{image_name}:{component_config.service.version}'`

## Critical Development Rules

1. **Shell Commands**:
   - **NEVER** use `cd foo && command` - this breaks shell state
   - **ALWAYS** use subshells: `(cd foo && command)` to isolate directory changes

2. **Code Quality**:
   - **MUST** run `uv run ./scripts/run-all-checks.sh` before committing
   - Run checks BEFORE manual fixes - many auto-fix issues automatically
   - Tools: Ruff (format/lint), Pyright (types), yamllint, pre-commit hooks

3. **Pulumi Safety**:
   - **ALWAYS** run `pulumi preview -s {stack} --diff --non-interactive` before deployment
   - Use `--non-interactive` flag to prevent terminal hanging
   - Use resource aliases when renaming to avoid recreation

4. **Git Workflow**:
   - All changes via feature branches and pull requests
   - Never commit directly to main branch
   - Use `hub sync` to clean up merged branches

## Stack Usage Patterns

- **Production (`prod`)**: Standard services - ingress, iot, obsidian, paperless, unifi, kubernetes, monitoring
- **Development (`dev`)**: Legacy services - monitoring, proxmox, s3 (from Synology migration)
- **Test (`test`)**: Experimental - kubernetes testing without affecting production

## Dependencies & Tools

- **Package management**: UV with workspace dependencies
- **Infrastructure**: Pulumi providers (cloudflare, kubernetes, proxmoxve, docker, etc.)
- **Configuration**: Pydantic models with JSON schema generation
- **Deployment**: Multiple providers with proper dependency management

- Never set cpu limits on pods
- Remember to configure python runtime options in `Pulumi.yaml` using uv and the venv in the root of the repository.
