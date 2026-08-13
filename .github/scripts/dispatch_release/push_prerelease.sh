#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"
: "${ACTION:?}"
: "${REF_NAME:?}"
: "${RELEASES:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_REPOSITORY:?}"

REPO_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}"

SUMMARY=$(echo "$RELEASES" | jq -r '[.[] | "\(.package)@\(.next)"] | join(", ")')

if [[ "$ACTION" == "continued-prerelease" ]]; then
  if [[ "$REF_NAME" != r/pre-* ]]; then
    echo "Error: continued-prerelease must be dispatched on the r/pre-* branch of an existing prerelease train (got '$REF_NAME')"
    exit 1
  fi
  BRANCH="$REF_NAME"
else
  # Same release timezone as the changelog heading dates (RELEASE_TIMEZONE in
  # scripts/release.py) so the branch name and headings never disagree.
  BRANCH="r/pre-$(TZ=America/Los_Angeles date +%Y.%m.%d)"
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

BRANCH_URL="${REPO_URL}/tree/${BRANCH}"
RUNS_URL="${REPO_URL}/actions/workflows/release_from_changelog.yml?query=$(jq -rn --arg q "branch:${BRANCH}" '$q | @uri')"

# An annotation as well as the summary: annotations surface on the run page
# itself, so the branch is one click away from wherever the dispatch was
# watched from.
echo "::notice::prerelease branch pushed: ${BRANCH_URL}"

{
  echo "## Prerelease pushed"
  echo ""
  echo "Branch: [\`${BRANCH}\`](${BRANCH_URL})"
  echo ""
  echo "Releases: ${SUMMARY}"
  echo ""
  echo "Dispatched the [\`release_from_changelog\`](${RUNS_URL}) workflow on the branch;"
  echo "approve the \`pypi\` environment deployments to upload the alphas."
} >> "$GITHUB_STEP_SUMMARY"
