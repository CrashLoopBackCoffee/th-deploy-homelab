# Agent Instructions for deploy-homelab

This document provides guidance for AI assistants working with code in this repository.

## Project Overview

This is a homelab infrastructure-as-code project that uses **Pulumi** with **Python** to manage and deploy various services across multiple environments. The project is built on top of **Proxmox** for virtualization and uses **MicroK8s** for the Kubernetes cluster. **Cloudflare** is used for DNS and other services.

The project follows a microservices architecture with each service in its own workspace. It emphasizes code quality, using tools like `ruff` for linting and `pyright` for type checking.

## Project Structure

### Core Architecture

- **Language**: Python 3.11+
- **Infrastructure**: Pulumi (Infrastructure as Code)
- **Package Management**: UV (Python package manager)
- **Environment Management**: Multiple Pulumi stacks (dev, test, prod)

### Service Organization

```
services/
├── backup/           # Restic and Rclone backup management
├── ingress/          # Cloudflared tunnels and ingress management
├── iot/              # IoT services (MQTT, Z-Wave, monitoring)
├── kubernetes/       # MicroK8s cluster management
├── monitoring/       # Monitoring stack (Prometheus, Grafana, etc.)
├── obsidian/         # Obsidian knowledge management
├── ollama/           # Ollama large language model service
├── paperless/        # Document management system
├── proxmox/          # Proxmox VE infrastructure with Ansible
├── s3/               # MinIO S3-compatible storage
└── unifi/            # UniFi network management
```

### Additional Repository Structure

- **`docs/`**: Contains example code and documentation for common patterns (e.g., `cnpg_postgres.py`)
- **`utils/`**: Shared utility modules for common functionality across services
- **`scripts/`**: Helper scripts for development and maintenance
- **`renovate.json5`**: Automated dependency update configuration

## Critical Development Rules

### 1. Shell Commands
- **NEVER** use `cd foo && command` as this changes the current working directory of the shell.
- **ALWAYS** use subshells instead: `(cd foo && command)` to isolate directory changes.
- **VIOLATION OF THIS RULE IS CRITICAL** - changing the working directory breaks the shell session for other commands.

### 2. Code Quality & Linting
- **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before making any commit to ensure code quality.
- **CRITICAL**: Run linting checks BEFORE manually fixing any code issues - many linters auto-fix problems automatically.
- The project uses multiple linting tools configured via pre-commit:
  - **Ruff**: Python code formatting (`ruff format`) and linting (`ruff check --fix`).
  - **Pyright**: Python type checking.
  - **Yamllint**: YAML file linting.
  - **Pre-commit hooks**: Various file checks (TOML, whitespace, etc.).
  - **Alloy format**: Grafana Alloy configuration formatting.
- **NEVER** commit code that fails linting checks.

### 3. Pulumi Commands & Safety

See the **`pulumi-operations`** skill for safety rules, all deployment commands, stack management, and resource rename patterns.

### 4. Python Code Style

See the **`python-pulumi-patterns`** skill for import conventions, type annotation rules, `LocalBaseModel` config patterns, and Kubernetes typed-dict notation.

### 5. Container Image Management

See the **`container-image-management`** skill for version field patterns, renovate annotation formats (github-releases, helm, endoflife-date), and config model conventions.

### 6. Helm Chart Management

See the **`helm-chart-management`** skill for the Chart vs Release decision rule, hook detection, and code examples.

### 7. Git Workflow
- Every change must happen on a feature branch and be performed via pull request.
- Use descriptive branch names (e.g., `feature/add-prometheus-monitoring`).
- Use `hub sync` to keep branches clean.
- Never commit directly to the main branch.

### 8. Kubernetes

See the **`python-pulumi-patterns`** skill for Kubernetes typed-dict notation and CPU limit rules.

## Common Commands

```bash
# Install/sync dependencies
uv sync

# Add a new dependency
uv add <package_name>

# Generate configuration schemas
uv run ./scripts/generate-config-schema

# CRITICAL: Run all linting and code quality checks (many tools auto-fix)
uv run ./scripts/run-all-checks.sh
```

For Pulumi deployment commands, see the **`pulumi-operations`** skill.

## Environment Management (Pulumi Stacks)

- **Production (`prod`)**: Primary homelab environment for most services.
- **Development (`dev`)**: Legacy services from a previous migration (`monitoring`, `proxmox`, `s3`).
- **Test (`test`)**: Experimental environment, especially for `kubernetes` changes.

## AI Assistant Guidelines

1.  **🚨 CRITICAL - Pulumi Safety**: See the **`pulumi-operations`** skill — always preview before deploying.
2.  **🚨 CRITICAL - Code Quality**: **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before committing.
3.  **Understand Service Context**: Each service in `services/` is self-contained but may have dependencies.
4.  **Follow Patterns**: Use the topic-specific skills for Pulumi, container images, Helm, and Python code style.
5.  **Configuration**: Remember to configure python runtime options in `Pulumi.yaml` using `uv` and the `venv` in the root of the repository.
6.  **MCP Interactive Feedback (Copilot)**:
    - When you want to ask a question, call the MCP `interactive_feedback`.
    - Before completing a request, call MCP `interactive_feedback`.
    - Keep calling MCP until the user's feedback is empty, then end the request.

## Documentation Maintenance

These instructions should be periodically validated against the repository state:
- Verify all services in the `services/` directory are documented
- Ensure all scripts and tools mentioned actually exist and work
- Check that code examples follow current project patterns
- Update tooling versions and commands as the project evolves
