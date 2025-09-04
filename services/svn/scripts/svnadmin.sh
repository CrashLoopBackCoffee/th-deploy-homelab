#!/usr/bin/env bash

set -euo pipefail

# Simple wrapper to run `svnadmin` inside the running svn deployment.
# Forwards all arguments as-is and supports piping data via stdin.
#
# Examples:
#   ./scripts/svnadmin.sh create /var/svn/repos/<repo>
#   gzip -dc repo.svndump.gz | ./scripts/svnadmin.sh load /var/svn/repos/<repo>
#
# Env vars:
#   NAMESPACE   Kubernetes namespace (default: svn)
#   DEPLOY      Deployment name (default: svn)
#   CONTAINER   Container name (default: svn)
#   WORKDIR     Working directory inside the container (default: /var/svn/repos)

NAMESPACE=${NAMESPACE:-svn}
DEPLOY=${DEPLOY:-svn}
CONTAINER=${CONTAINER:-svn}
WORKDIR=${WORKDIR:-/var/svn/repos}

SVNADMIN=/usr/local/subversion/bin/svnadmin

# Detect if stdin is piped (non-tty) to enable interactive mode for kubectl exec
interactive_flag=()
if [ ! -t 0 ]; then
  interactive_flag=(-i)
fi

# Build a safely-escaped argument string for sh -lc
args_escaped=""
for a in "$@"; do
  # shellcheck disable=SC2059
  args_escaped+=" "$(printf %q "$a")
done

cmd="cd ${WORKDIR} && exec ${SVNADMIN}${args_escaped}"

# Forward into container with working directory applied
kubectl -n "${NAMESPACE}" exec "${interactive_flag[@]}" -c "${CONTAINER}" deploy/"${DEPLOY}" -- \
  /bin/sh -lc "$cmd"
