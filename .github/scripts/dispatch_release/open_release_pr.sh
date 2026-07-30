#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"
: "${ACTION:?}"
: "${REF_NAME:?}"
: "${RELEASES:?}"
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
  echo "Merging this PR lands the versions above for release: the push to \`${BASE}\`"
  echo "triggers the \`release_from_changelog\` workflow, which builds each package and"
  echo "then waits for \`pypi\` environment approval before uploading; the tag and"
  echo "GitHub release are created only after a successful upload. If a publish"
  echo "fails, fix the problem on top of the changelog bump — the next push retries"
  echo "automatically."
} > "$BODY_FILE"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
# Stage only what materialization is expected to touch: rewritten changelogs
# and consumed news fragments (towncrier already stages the deletions).
git add -A -- CHANGELOG.md news 'packages/*/CHANGELOG.md' 'packages/*/news'
if git diff --cached --quiet; then
  echo "Error: materialization produced no changes; nothing to release."
  exit 1
fi
git commit -m "Materialize changelogs for ${SUMMARY} (${ACTION})"
# The token is supplied via gh's credential helper so it never appears in a
# remote URL or process argv.
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push origin "HEAD:refs/heads/${BRANCH}"

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
