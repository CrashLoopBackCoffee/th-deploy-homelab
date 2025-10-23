#!/usr/bin/env bash

set -euo pipefail

docker run --rm -v "$PWD":/opt prom/snmp-generator generate \
  -m /opt/mibs \
  -g /opt/generator.yaml \
  -o /opt/snmp.yml \
  --no-fail-on-parse-errors
