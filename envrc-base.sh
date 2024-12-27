#!/usr/bin/env bash

# Run self update as first step
"${DEPLOY_BASE_ROOT}/bin/update-deploy-base.sh"

# This repo uses uv for dependency management
uv sync --locked

# Add helper scripts in deploy-base to PATH
export PATH="${DEPLOY_BASE_ROOT}/bin:${PATH}"


# Suppress bogus warning messages like
# resource plugin pulumi-python is expected to have version >=3.6.0, but has 0.1.0;
# the wrong version may be on your path, or this may be a bug in the plugin
export PULUMI_DEV=1

# Suppress pulumi phone home
export PULUMI_SKIP_UPDATE_CHECK=true

# Make pyright fast again (skip broken update check with proxy)
export PYRIGHT_PYTHON_IGNORE_WARNINGS=1

# Enable patch force to force pulumi ownership when using server side apply (default in pulumi-kubernetes>=4.0)
# https://www.pulumi.com/registry/packages/kubernetes/how-to-guides/managing-resources-with-server-side-apply/#handle-field-conflicts-on-existing-resources
export PULUMI_K8S_ENABLE_PATCH_FORCE=true


#  check if repo is enabled for pre-commit by checking if present in venv
if [ -f "./.venv/bin/pre-commit" ] && [ "${SKIP_PRE_COMMIT:-false}" != "true" ]; then

  #  link config if not present
  if [ ! -f ".pre-commit-config.yaml" ]; then
    echo -e "${GREEN}Linking .pre-commit-config.yaml$NC"
    ln -fs "${DEPLOY_BASE_ROOT}/.pre-commit-config.yaml" .
  fi

  # Install pre-commit hook
  if [ ! -f ".git/hooks/pre-commit" ]; then
    echo -e "${GREEN}Installing pre-commit hook$NC"
    ./.venv/bin/pre-commit install
  fi

  # Install pre-push hook
  if [ ! -f ".git/hooks/pre-push" ]; then
    echo -e "${GREEN}Installing pre-push hook$NC"
    ./.venv/bin/pre-commit install --hook-type pre-push
  fi

  # Install hooks to save time on first commit
  echo "Ensuring pre-commit hooks are installed"
  ./.venv/bin/pre-commit install-hooks
else
  echo -e "${YELLOW}Pre-commit not enabled for this repo!$NC"
  echo -e "To enable pre-commit, run: ${PURPLE}poetry add --group dev pre-commit filelock distlib pyright ruff yamllint$NC"
fi

# Generate config schema
./.venv/bin/python3 "${DEPLOY_BASE_ROOT}/bin/generate-config-schema"
