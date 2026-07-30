#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"
: "${ACTION:?}"
: "${REF_NAME:?}"
: "${RELEASES:?}"
: "${GITHUB_RUN_ID:?}"

SUMMARY=$(echo "$RELEASES" | jq -r '[.[] | "\(.package)@\(.next)"] | join(", ")')

if [[ "$ACTION" == "continued-prerelease" ]]; then
  if [[ "$REF_NAME" != r/pre-* ]]; then
    echo "Error: continued-prerelease must be dispatched on the r/pre-* branch of an existing prerelease train (got '$REF_NAME')"
    exit 1
  fi
  BRANCH="$REF_NAME"
else
  BRANCH="r/pre-$(date -u +%Y.%m.%d)"
  if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    BRANCH="${BRANCH}-${GITHUB_RUN_ID}"
  fi
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
# Stage only what materialization is expected to touch: rewritten changelogs
# and consumed news fragments (towncrier already stages the deletions).
git add -A -- CHANGELOG.md news 'packages/*/CHANGELOG.md' 'packages/*/news'
if git diff --cached --quiet; then
  echo "Error: materialization produced no changes; nothing to push."
  exit 1
fi
git commit -m "Materialize changelogs for ${SUMMARY} (${ACTION})"
# The token is supplied via gh's credential helper so it never appears in a
# remote URL or process argv.
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push origin "HEAD:refs/heads/${BRANCH}"

# Pushes made with GITHUB_TOKEN do not fire on-push workflows, so dispatch the
# changelog check explicitly. Building is automatic; the upload itself still
# waits for pypi environment approval.
gh workflow run release_from_changelog.yml --ref "$BRANCH"

{
  echo "## Prerelease pushed"
  echo ""
  echo "Branch: \`${BRANCH}\`"
  echo ""
  echo "Releases: ${SUMMARY}"
  echo ""
  echo "Dispatched the \`release_from_changelog\` workflow on the branch; approve the"
  echo "\`pypi\` environment deployments to upload the alphas."
} >> "$GITHUB_STEP_SUMMARY"
