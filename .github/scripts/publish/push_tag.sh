#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${GH_TOKEN:?}"
: "${GITHUB_REPOSITORY:?}"

# Tag the published commit and push it. Runs only after a successful PyPI
# upload — the tag's existence is what marks a version as published. Pushing
# an identical existing tag is a no-op (safe re-runs); a same-name tag on a
# different commit is rejected by git, which means another run already
# published this version from a different commit — investigate, don't force.
git tag --force "$TAG"
git push "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "refs/tags/${TAG}"
