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
# Stage the changelog rewrites (including first-release creations); a
# directory pathspec with a wildcard never matches, so name the files. The
# consumed news fragments are already staged by towncrier's git rm, and
# `commit -a` below picks up any tracked change it left unstaged — while
# never committing untracked stray files.
git add -- CHANGELOG.md 'packages/*/CHANGELOG.md'
if git diff --cached --quiet && git diff --quiet; then
  echo "Error: materialization produced no changes; nothing to push."
  exit 1
fi
git commit -a -m "Materialize changelogs for ${SUMMARY} (${ACTION})"
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
