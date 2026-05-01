#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${GH_TOKEN:?}"

gh workflow run publish.yml -f tag="$TAG"
