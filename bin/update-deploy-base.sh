#!/usr/bin/env bash

set -eu

RED="\033[31m"
ENDCOLOR="\033[0m"

cd "${BASEDIR}/../deploy-base"

FETCH=true

# Skip update check if requested. This is used within CI where it's
# guarenteed to be up to date.
SKIP_DEPLOY_BASE_UPDATE_CHECK=${SKIP_DEPLOY_BASE_UPDATE_CHECK:=false}
if [ "${SKIP_DEPLOY_BASE_UPDATE_CHECK}" == "true" ]; then
  echo "Skipping update check"
  exit
fi

# Validate that the working dir is clean. If not emit a warning and skip update.
if [ -n "$(git status --porcelain)" ]; then
  echo -e "${RED}Warning, deploy-base working dir is unclean!${ENDCOLOR}"
  FETCH=false
fi

# Check if master is checked out. If not emit a warning and skip update.
if [ "$(git rev-parse --abbrev-ref HEAD)" != "master" ]; then
  echo -e "${RED}Warning, current HEAD is not master!${ENDCOLOR}"
  FETCH=false
fi

# Check if we updated within the last 12h. If we did skip the update.
# 12h should be enough to only update once a working day.
CURRENT_TIMESTAMP="$(date '+%s')"
if [ -e .last-fetched ]; then
  LAST_FETCHED=$(cat .last-fetched)

  DIFF=$((${CURRENT_TIMESTAMP} - ${LAST_FETCHED}))
  if [ ${DIFF} -lt 43200 ]; then
    FETCH=false
  fi
fi

if [ "${FETCH}" != "true" ]; then
  exit
fi

echo "Updating deploy-base"
echo "${CURRENT_TIMESTAMP}" > .last-fetched

git fetch origin
git reset --hard origin/master
