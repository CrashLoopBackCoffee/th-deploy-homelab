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

2. **Configuration Management**:

   - Each service has a `config.py` file with Pydantic models for type-safe configuration
   - Configuration schemas are automatically generated and linked to VS Code YAML validation
   - Use `ComponentConfig.model_validate(p.Config().get_object('config'))` pattern

3. **Python Code**:
   - Use type hints consistently
   - Follow PEP 8 style guidelines
   - Prefer composition over inheritance for Pulumi components
   - Use dataclasses or Pydantic models for structured data

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

- `dev`: Development environment
- `test`: Testing environment
- `prod`: Production environment

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
   - Never use `cd foo && command` patterns as this changes the current working directory of the shell
   - Use subshells instead: `(cd foo && command)` to isolate directory changes
   - Alternatively, use explicit paths or tools that support working directory arguments

7. **Terminal Usage**:
   - Always use the `run_in_terminal` tool instead of trying to reference specific terminal IDs
   - Avoid using `get_terminal_output` with specific IDs as they may become invalid
   - Let VS Code manage terminal sessions automatically

## Common Commands

```bash
# Install dependencies
uv sync

# Generate configuration schemas
uv run ./scripts/generate-config-schema

# Run all checks
uv run ./scripts/run-all-checks.sh

# Deploy a service
cd services/{service-name}
pulumi up --stack {stack-name}

# Preview changes
pulumi preview --stack {stack-name}
```

## AI Assistant Guidelines

When working on this project:

1. **Understand the Service Context**: Each service is self-contained but may depend on others
2. **Follow Pulumi Patterns**: Use the established patterns for providers, resources, and configuration
3. **Maintain Type Safety**: Always use proper type hints and Pydantic models
4. **Consider Dependencies**: Be aware of inter-service dependencies and deployment order
5. **Environment Awareness**: Consider which stack/environment changes affect
6. **Security First**: Handle secrets properly and follow security best practices
