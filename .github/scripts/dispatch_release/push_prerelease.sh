#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"
: "${ACTION:?}"
: "${REF_NAME:?}"
: "${RELEASES:?}"
: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_RUN_ID:?}"

SUMMARY=$(echo "$RELEASES" | jq -r '[.[] | "\(.package)@\(.next)"] | join(", ")')

if [[ "$ACTION" == "continued-prerelease" ]]; then
  if [[ "$REF_NAME" != r/* ]]; then
    echo "Error: continued-prerelease must be dispatched on the r/* branch of an existing prerelease train (got '$REF_NAME')"
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
git add -A
git commit -m "Materialize changelogs for ${SUMMARY} (${ACTION})"
git push "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "HEAD:refs/heads/${BRANCH}"

# Pushes made with GITHUB_TOKEN do not fire on-push workflows, so dispatch the
# changelog check explicitly to publish the alphas.
gh workflow run release_from_changelog.yml --ref "$BRANCH"

{
  echo "## Prerelease pushed"
  echo ""
  echo "Branch: \`${BRANCH}\`"
  echo ""
  echo "Releases: ${SUMMARY}"
  echo ""
  echo "Dispatched the \`release_from_changelog\` workflow on the branch to publish the alphas."
} >> "$GITHUB_STEP_SUMMARY"
