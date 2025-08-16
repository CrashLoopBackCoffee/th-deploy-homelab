# GitHub Copilot Instructions for th-deploy-homelab

## Project Overview

This is a homelab infrastructure-as-code project that uses **Pulumi** with **Python** to manage and deploy various services across multiple environments. The project follows a microservices architecture with each service in its own workspace.

## Project Structure

### Core Architecture

- **Language**: Python 3.11+
- **Infrastructure**: Pulumi (Infrastructure as Code)
- **Package Management**: UV (Python package manager)
- **Environment Management**: Multiple Pulumi stacks (dev, test, prod)

### Service Organization

```
services/
├── ingress/          # Cloudflared tunnels and ingress management
├── iot/              # IoT services (MQTT, Z-Wave, monitoring)
├── kubernetes/       # MicroK8s cluster management
├── monitoring/       # Monitoring stack (Prometheus, Grafana, etc.)
├── obsidian/         # Obsidian knowledge management
├── paperless/        # Document management system
├── proxmox/          # Proxmox VE infrastructure with Ansible
├── s3/               # MinIO S3-compatible storage
└── unifi/            # UniFi network management
```

## Development Guidelines

### Code Style & Patterns

1. **Pulumi Resources**:

   - Always use typed configuration models for Pulumi configs
   - When renaming a resource, preserve state with aliases via `pulumi.ResourceOptions(aliases=[pulumi.Alias(name='old-name')])` to avoid recreation

2. **Configuration Management**:

   - Each service has a `config.py` file with Pydantic models for type-safe configuration
   - Configuration schemas are automatically generated and linked to VS Code YAML validation
   - Use `ComponentConfig.model_validate(p.Config().get_object('config'))` pattern

3. **Python Code**:
   - Use type hints consistently
   - Follow PEP 8 style guidelines
   - Prefer composition over inheritance for Pulumi components
   - Use dataclasses or Pydantic models for structured data
   - Keep dependency lists in `pyproject.toml` sorted alphabetically for readability and smaller diffs
   - **Import Style**: Follow project import conventions:
     - Use `import ...` for external libraries (e.g., `import json`, `import os`)
     - Use `from ... import ...` for internal/project imports
     - Use standard abbreviations (and ONLY these):
       - `import typing as t`
       - `import pulumi as p`
       - `import pulumi_kubernetes as k8s`
       - `import collections.abc as c`
     - Use full module names for other imports: `import pathlib`, `import concurrent.futures`

4. **Container Image Management**:
   - **NEVER** hardcode image tags in Python code
   - **ALWAYS** include image versions in the configuration model with appropriate field names (e.g., `redis_version`, `restic_version`)
   - **ALWAYS** verify version numbers against the actual releases before using them - don't rely on prior knowledge or assumptions
   - **PREFER official container images** over runtime tool downloads when available (e.g., `registry.k8s.io/conformance` for kubectl instead of downloading kubectl binaries)
   - **ALWAYS** add renovate comments above version fields in `Pulumi.{stack}.yaml` using the format:
     ```yaml
     # renovate: datasource=github-releases packageName=<owner>/<repo> versioning=semver
     <service>-version: <version>
     ```
   - **Prefer `github-releases` datasource** when the component has proper GitHub releases for better changelog information in Renovate PRs
   - **Fall back to `docker` datasource** only when GitHub releases are not available or don't match the image versions
   - **IMPORTANT**: Verify that GitHub release versions exactly match Docker image tag versions before switching datasources
   - **Best Practice**: When adding a new service, pick one version below the current latest to validate Renovate configuration quickly after merge
   - Use the config value in Python code: `f'{image_name}:{component_config.service.version}'`

### File Naming Conventions

- `__main__.py`: Main Pulumi program entry point for each service
- `config.py`: Pydantic configuration models
- `pyproject.toml`: Service-specific dependencies and metadata
- `Pulumi.{stack}.yaml`: Stack-specific configuration files

### Common Patterns

2. **Resource Dependencies**:

   - Prefer implicit dependencies over explicit ones
   - Use Pulumi's dependency management (`depends_on`, `Output.apply()`)

3. **Secret Management**:
   - Use Pulumi secrets for sensitive data
   - Reference secrets through configuration models with `.value` accessor

## Service-Specific Guidelines

### Kubernetes Service

- Manages MicroK8s cluster deployment on Proxmox VMs
- Includes CSI drivers, MetalLB, Traefik, and cert-manager
- Use Kubernetes provider for resource management

### Monitoring Service

- Deploys observability stack (Prometheus, Grafana, Alertmanager)
- Follow monitoring best practices (labels, metrics naming)
- Include dashboards and alerts as code

### Proxmox Service

- Combines Pulumi for VM provisioning and Ansible for configuration
- Ansible playbooks in `playbooks/` directory
- VM templates and cloud-init configurations

### IoT Service

- MQTT broker (Mosquitto) configuration
- Z-Wave controller integration
- Metrics collection with mqtt2prometheus

## Environment Management

### Pulumi Stacks

The homelab uses different stack configurations based on service requirements:

**Production Stack (`prod`)** - Primary homelab environment:
- **Standard services**: `ingress`, `iot`, `obsidian`, `paperless`, `unifi`
- **Lower-level services**: `kubernetes`, `monitoring` (also has `prod`)
- Used for stable, production-ready deployments

**Development Stack (`dev`)** - Legacy from Synology migration:
- **Legacy services**: `monitoring`, `proxmox`, `s3`
- Contains configurations migrated from the previous Synology-based homelab
- Used for services that haven't been fully migrated to production patterns

**Test Stack (`test`)** - Experimental environment:
- **Experimental services**: `kubernetes`
- Used for testing new configurations without affecting production services
- Allows safe experimentation on lower-level infrastructure components

### Stack Selection Guidelines

- **Most services**: Use `prod` stack for standard homelab operations
- **Infrastructure experimentation**: Use `test` stack for kubernetes changes
- **Legacy components**: Use `dev` stack for services still being migrated
- **New services**: Should typically start with `prod` stack unless experimental

### Configuration

- Stack-specific configs in `Pulumi.{stack}.yaml`
- Shared configuration through workspace dependencies
- Schema validation enabled through VS Code settings

## Dependencies & Tools

### Core Dependencies

- Pulumi providers: cloudflare, docker, kubernetes, proxmoxve, random, etc.
- Python packages managed through UV
- Workspace dependencies between services

### Development Tools

- `scripts/generate-config-schema`: Generate JSON schemas for Pulumi configs
- `scripts/run-all-checks.sh`: Run linting, type checking, and tests
- `scripts/alloy-fmt`: Format Grafana Alloy configurations

## Documentation Links

### Pulumi Core

- [Pulumi Documentation](https://www.pulumi.com/docs/) - Main documentation hub
- [Pulumi Python SDK](https://www.pulumi.com/docs/languages-sdks/python/) - Python-specific guides and reference
- [Pulumi Configuration](https://www.pulumi.com/docs/concepts/config/) - Configuration and secrets management
- [Pulumi Stacks](https://www.pulumi.com/docs/concepts/stack/) - Stack management and environments
- [Pulumi Outputs](https://www.pulumi.com/docs/concepts/inputs-outputs/) - Working with inputs and outputs

### Pulumi Providers

The project uses the following Pulumi providers:

- [Cloudflare Provider](https://www.pulumi.com/registry/packages/cloudflare/) - DNS, tunnels, and CDN management
- [Command Provider](https://www.pulumi.com/registry/packages/command/) - Execute shell commands and scripts
- [Docker Provider](https://www.pulumi.com/registry/packages/docker/) - Container and image management
- [Kubernetes Provider](https://www.pulumi.com/registry/packages/kubernetes/) - Kubernetes resource management
- [MinIO Provider](https://www.pulumi.com/registry/packages/minio/) - S3-compatible object storage
- [1Password Provider](https://www.pulumi.com/registry/packages/onepassword/) - Secret management integration
- [PostgreSQL Provider](https://www.pulumi.com/registry/packages/postgresql/) - Database management
- [Proxmox VE Provider](https://www.pulumi.com/registry/packages/proxmoxve/) - Virtual machine and container management
- [Random Provider](https://www.pulumi.com/registry/packages/random/) - Generate random values and passwords
- [TLS Provider](https://www.pulumi.com/registry/packages/tls/) - Certificate and key management

### Service-Specific Documentation

- [MicroK8s Documentation](https://microk8s.io/docs) - Lightweight Kubernetes distribution
- [Proxmox VE Documentation](https://pve.proxmox.com/pve-docs/) - Virtualization platform
- [Cloudflare Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) - Secure ingress tunneling
- [Grafana Documentation](https://grafana.com/docs/) - Monitoring and observability
- [Prometheus Documentation](https://prometheus.io/docs/) - Metrics collection and alerting
- [Mosquitto Documentation](https://mosquitto.org/documentation/) - MQTT broker
- [Traefik Documentation](https://doc.traefik.io/traefik/) - Reverse proxy and load balancer
- [cert-manager Documentation](https://cert-manager.io/docs/) - Certificate management for Kubernetes
- [MetalLB Documentation](https://metallb.universe.tf/) - Load balancer for bare metal Kubernetes

### Development Tools

- [UV Documentation](https://docs.astral.sh/uv/) - Python package and project manager
- [Pydantic Documentation](https://docs.pydantic.dev/) - Data validation and settings management
- [Ansible Documentation](https://docs.ansible.com/) - Configuration management and automation

## Best Practices

1. **Git Workflow**:

   - Every change to the repository must happen on a feature branch and be performed via pull request
   - Use descriptive branch names (e.g., `feature/add-prometheus-monitoring`, `fix/kubernetes-metallb-config`)
   - When pushing to the remote branch ensure the local branch tracks it (aka using `--set-upstream`)
   - Use `hub sync` to fetch updates from GitHub. In combination with local tracking branches this ensures that local branches that refer to merged pull requests are cleaned up automatically
   - Never commit directly to the main branch

2. **Infrastructure as Code**:

   - All infrastructure changes should go through Pulumi
   - Use preview mode before applying changes
   - Document resource purposes and dependencies

3. **Configuration**:

   - Keep secrets in Pulumi secret storage
   - Use environment-specific configuration files
   - Validate configurations with Pydantic models

4. **Testing**:

   - Test configuration parsing and validation
   - Validate generated configurations

5. **Documentation**:

   - Update this file when adding new services or patterns
   - Document complex infrastructure relationships
   - Include deployment and troubleshooting guides

6. **Shell Commands**:
   - **NEVER** use `cd foo && command` patterns as this changes the current working directory of the shell
   - **ALWAYS** use subshells instead: `(cd foo && command)` to isolate directory changes
   - This is critical: `cd services/iot && pulumi stack ls` is WRONG, use `(cd services/iot && pulumi stack ls)` instead
   - Alternatively, use explicit paths or tools that support working directory arguments
   - **VIOLATION OF THIS RULE IS CRITICAL** - changing working directory breaks the shell session for other commands

7. **Linting and Code Quality**:
   - **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before making any commit to ensure code quality
   - **CRITICAL**: Run linting checks BEFORE manually fixing any code issues - many linters auto-fix problems automatically
   - The project uses multiple linting tools configured via pre-commit:
     - **Ruff**: Python code formatting (`ruff format`) and linting (`ruff check --fix`) with auto-fixes for import ordering, code style, etc.
     - **Pyright**: Python type checking for type safety validation
     - **Yamllint**: YAML file linting with strict validation
     - **Pre-commit hooks**: Various file checks (TOML validation, whitespace trimming, end-of-file fixing, etc.)
     - **Alloy format**: Grafana Alloy configuration file formatting
   - **Auto-fix capabilities**: Many tools automatically fix issues including code formatting, import ordering, whitespace, and file endings
   - **NEVER** commit code that fails linting checks - always ensure `run-all-checks.sh` succeeds
   - If linting fails, run the script again as it often fixes issues on multiple passes
   - Use `uv run ./scripts/run-all-checks.sh` (not just `./scripts/run-all-checks.sh`) to ensure proper dependency management

8. **Pulumi Commands**:
   - **ALWAYS** use `--non-interactive` flag with Pulumi commands to prevent interactive mode from breaking terminal integration
   - This applies to `pulumi up`, `pulumi preview`, and other commands that might prompt for user input
   - Interactive mode can cause VS Code terminal sessions to hang or become unresponsive

9. **Terminal Initialization**:
   - **CRITICAL**: Every new Copilot session gets a fresh terminal that must be initialized before use
   - The first terminal command in any session triggers extensive direnv loading (package resolution, schema generation, pre-commit setup, etc.)
   - **ALWAYS** run a dummy initialization command before executing the actual intended command
   - Use `echo "Initializing terminal..."` or similar as the first command in any new session
   - Wait for the direnv loading to complete before running subsequent commands
   - This prevents the actual command from being interrupted or failing due to environment setup

## Common Commands

```bash
# ALWAYS initialize terminal first in new sessions
echo "Initializing terminal..."

# Install dependencies
uv sync

# Generate configuration schemas
uv run ./scripts/generate-config-schema

# CRITICAL: Run all linting and code quality checks
# ALWAYS run this before committing - many tools auto-fix issues automatically
uv run ./scripts/run-all-checks.sh

# Deploy a service (using subshell to isolate directory change)
# IMPORTANT: ALWAYS run preview first to check for unexpected changes
(cd services/{service-name} && pulumi preview -s {stack-name} --diff --non-interactive)
(cd services/{service-name} && pulumi up --stack {stack-name} --non-interactive --skip-preview)

# Preview changes (using subshell to isolate directory change)
(cd services/{service-name} && pulumi preview --stack {stack-name} --non-interactive)

# Preview changes with diff to see actual modifications
(cd services/{service-name} && pulumi preview -s {stack-name} --diff --non-interactive)

# List available stacks for a service
(cd services/{service-name} && pulumi stack ls)

# Check stack configuration
(cd services/{service-name} && pulumi config --stack {stack-name})
```

## AI Assistant Guidelines

When working on this project:

10. **MCP Interactive Feedback**:
   - Whenever you want to ask a question, always call the MCP interactive_feedback.
   - Whenever you’re about to complete a user request, call the MCP interactive_feedback instead of simply ending the process.
   - Keep calling MCP until the user’s feedback is empty, then end the request.
   - This ensures interactive, user-driven completion and review of all Copilot actions.

1. **🚨 CRITICAL - Terminal Initialization**: **ALWAYS** run a dummy command (`echo "Initializing terminal..."`) as the very first command in any new Copilot session, then wait for direnv loading to complete before running actual commands. This prevents commands from being interrupted by environment setup.

2. **🚨 CRITICAL - Pulumi Safety**: **ALWAYS** run `pulumi preview` with `--diff` flag before any `pulumi up` command to check for unexpected changes. Never deploy without reviewing the preview first.

3. **🚨 CRITICAL - Code Quality**: **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before making any changes to ensure all linting and code quality checks pass. Many tools auto-fix issues automatically, so run this first before manually editing code.

4. **Understand the Service Context**: Each service is self-contained but may depend on others
5. **Follow Pulumi Patterns**: Use the established patterns for providers, resources, and configuration
6. **Maintain Type Safety**: Always use proper type hints and Pydantic models
7. **Consider Dependencies**: Be aware of inter-service dependencies and deployment order
8. **Environment Awareness**: Consider which stack/environment changes affect
9. **Security First**: Handle secrets properly and follow security best practices
