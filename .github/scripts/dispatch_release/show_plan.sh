#!/usr/bin/env bash
set -euo pipefail

: "${RELEASES:?}"
: "${ACTION:?}"

{
  echo "## Approved release plan"
  echo ""
  echo "Action: \`${ACTION}\`"
  echo ""
  echo "| Package | Current | Next | Tag |"
  echo "|---------|---------|------|-----|"
  echo "$RELEASES" | jq -r '.[] | "| `\(.package)` | `\(if .current == "" then "<none>" else .current end)` | `\(.next)` | `\(.tag)` |"'
} >> "$GITHUB_STEP_SUMMARY"

echo "$RELEASES" | jq .
