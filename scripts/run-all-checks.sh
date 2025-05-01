#!/usr/bin/env bash

set -x
set -eu

rc=0

BASEDIR=$(git rev-parse --show-toplevel)

cd "${BASEDIR}"

.venv/bin/pre-commit run --all-files || rc=$?

exit $rc
