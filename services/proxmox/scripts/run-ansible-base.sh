#!/usr/bin/env bash

set -eu

SCRIPT_NAME=$(basename "$0")
ENVIRONMENT=$(echo "$SCRIPT_NAME" | sed -e 's/^run-ansible-//' -e 's/\.sh$//')

INVENTORY="inventory/${ENVIRONMENT}"

op run --no-masking --env-file="${INVENTORY}/secrets.env" -- uv run ansible-playbook -i "${INVENTORY}" "$@"
