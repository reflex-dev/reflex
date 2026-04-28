#!/usr/bin/env bash
set -euo pipefail

: "${EVENT_NAME:?}"

if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
  : "${DISPATCH_PACKAGE:?}"
  printf 'packages=["%s"]\n' "$DISPATCH_PACKAGE" >> "$GITHUB_OUTPUT"
  exit 0
fi

PACKAGES=()
for pkg in reflex-components-internal reflex-site-shared; do
  if git diff --name-only HEAD~1 HEAD -- "packages/$pkg/" | grep -q .; then
    PACKAGES+=("\"$pkg\"")
  fi
done

JOINED=$(IFS=,; echo "${PACKAGES[*]:-}")
echo "packages=[$JOINED]" >> "$GITHUB_OUTPUT"
