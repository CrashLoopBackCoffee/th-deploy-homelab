#!/usr/bin/env bash

set -eu

cd "$(dirname "$0")"

ansible-playbook -i inventory/prod/hosts.yaml playbooks/main.yaml "$@"
