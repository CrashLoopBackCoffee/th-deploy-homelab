# Setup Project Action

This is a reusable GitHub Action that sets up the complete environment needed for working with the th-deploy-homelab project.

## What it does

1. **Sets up Python** - Installs the specified Python version (defaults to 3.11)
2. **Installs UV** - Installs the UV package manager using `astral-sh/setup-uv@v6`
3. **Syncs dependencies** - Runs `uv sync` to install all project dependencies
4. **Installs Grafana Alloy** - Downloads and installs the Grafana Alloy tool for configuration formatting

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `python-version` | Python version to install | No | `3.11` |
| `alloy-version` | Grafana Alloy version to install | No | `v1.10.0` |

## Usage

### Basic usage

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: ./.github/actions/setup-project
```

### With custom versions

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: ./.github/actions/setup-project
    with:
      python-version: '3.12'
      alloy-version: 'v1.11.0'
```

## What tools are available after setup

After running this action, the following tools will be available:

- `python` - Python interpreter
- `uv` - UV package manager
- `alloy` - Grafana Alloy configuration tool
- All Python packages from `pyproject.toml` via `uv sync`

This provides the same environment as the linter workflow and allows GitHub Copilot agents to have consistent project dependencies.
