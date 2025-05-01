#!/usr/bin/env bash

set -x
set -eu

black .
ruff check --fix
