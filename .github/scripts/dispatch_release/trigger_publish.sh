#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${REF:?}"
: "${GH_TOKEN:?}"

gh workflow run publish.yml --ref "$REF" -f tag="$TAG"
