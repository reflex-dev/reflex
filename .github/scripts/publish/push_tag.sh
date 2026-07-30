#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${GH_TOKEN:?}"

# Tag the published commit and push it. Runs only after a successful PyPI
# upload — the tag's existence is what marks a version as published. Pushing
# an identical existing tag is a no-op (safe re-runs); a same-name tag on a
# different commit is rejected by git, which means another run already
# published this version from a different commit — investigate, don't force.
#
# The token is supplied via gh's credential helper so it never appears in a
# remote URL or process argv.
git tag --force "$TAG"
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push origin "refs/tags/${TAG}"
