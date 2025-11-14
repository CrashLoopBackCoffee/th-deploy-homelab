#!/usr/bin/env bash

set -euo pipefail

BASEURL="https://raw.githubusercontent.com/cloudnative-pg/artifacts/refs/heads/main/image-catalogs"

CATALOG_FILES=(
    "catalog-minimal-bookworm.yaml"
    "catalog-minimal-bullseye.yaml"
    "catalog-minimal-trixie.yaml"
    "catalog-standard-bookworm.yaml"
    "catalog-standard-bullseye.yaml"
    "catalog-standard-trixie.yaml"
    "catalog-system-bookworm.yaml"
    "catalog-system-bullseye.yaml"
    "catalog-system-trixie.yaml"
)

for FILE in "${CATALOG_FILES[@]}"; do
    curl -fSL "${BASEURL}/${FILE}" -o "./${FILE}"
done
