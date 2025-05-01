#!/usr/bin/env bash

set -x
set -eu

rc=0

.venv/bin/pre-commit run --all-files || rc=$?

exit $rc
