#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"
: "${ACTION:?}"
: "${REF_NAME:?}"
: "${RELEASES:?}"
: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_RUN_ID:?}"

# Final versions publish from main — except hotfix trains, which publish
# directly from their r/hotfix/** branch, so the PR targets it instead.
BASE="main"
if [[ "$REF_NAME" == r/hotfix/* ]]; then
  BASE="$REF_NAME"
fi

BRANCH="release/${ACTION}-${GITHUB_RUN_ID}"
SUMMARY=$(echo "$RELEASES" | jq -r '[.[] | "\(.package)@\(.next)"] | join(", ")')

BODY_FILE="${RUNNER_TEMP}/release_pr_body.md"
{
  echo "Materialized changelogs for release action \`${ACTION}\` (dispatched on \`${REF_NAME}\`)."
  echo ""
  echo "| Package | Current | Next | Tag |"
  echo "|---------|---------|------|-----|"
  echo "$RELEASES" | jq -r '.[] | "| `\(.package)` | `\(if .current == "" then "<none>" else .current end)` | `\(.next)` | `\(.tag)` |"'
  echo ""
  echo "Merging this PR is the release approval: the push to \`${BASE}\` triggers the"
  echo "\`release_from_changelog\` workflow, which publishes each version above and only"
  echo "then pushes its tag and creates the GitHub release. If a publish fails, fix the"
  echo "problem on top of the changelog bump — the next push retries automatically."
} > "$BODY_FILE"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
git commit -m "Materialize changelogs for ${SUMMARY} (${ACTION})"
git push "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "HEAD:refs/heads/${BRANCH}"

PR_URL=$(gh pr create --base "$BASE" --head "$BRANCH" --title "Release ${SUMMARY}" --body-file "$BODY_FILE")

# The PR only rewrites changelogs and deletes consumed news fragments, so the
# changelog fragment check does not apply. Label failure is non-fatal.
gh pr edit "$PR_URL" --add-label skip-changelog || echo "::notice::could not add skip-changelog label to $PR_URL"

{
  echo "## Release PR opened"
  echo ""
  echo "$PR_URL"
  echo ""
  echo "Releases: ${SUMMARY}"
} >> "$GITHUB_STEP_SUMMARY"
