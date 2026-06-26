#!/usr/bin/env bash
#
# Delete GitHub Releases whose body starts with one of the auto-release
# markers ("Automated release for" / "Dispatch release for") while KEEPING the
# underlying git tags.
#
# These Release entries are created by the automated/dispatch release CI
# workflows (one per sub-package version bump) and clutter the Releases page.
# Deleting the Release object removes only the GitHub Releases UI entry; the
# git tag -- and therefore the commit it points at and anything that resolves
# it (pip installs, changelog links, etc.) -- is left untouched, because we
# never pass `gh release delete --cleanup-tag`.
#
# Usage:
#   scripts/delete_automated_releases.sh                  # dry run: list matches, delete nothing
#   scripts/delete_automated_releases.sh --apply          # delete (asks for confirmation once)
#   scripts/delete_automated_releases.sh --apply --yes    # delete without the confirmation prompt
#   REPO=owner/name scripts/delete_automated_releases.sh  # target a different repo (default below)
#   scripts/delete_automated_releases.sh --repo=owner/name --apply
#
# Requires: gh (https://cli.github.com/, authenticated via `gh auth login`) and jq.

set -euo pipefail

REPO="${REPO:-reflex-dev/reflex}"

# Body prefixes that identify an auto-generated release. Matching is exact
# (no leading-whitespace tolerance). Add/remove entries here to adjust scope.
PREFIXES=("Automated release for" "Dispatch release for")

usage() {
  # Print the header comment block (from line 3 to the first non-comment line),
  # stripping the leading "# " so --help reads as plain help text.
  awk 'NR>=3 { if (/^#/) { sub(/^# ?/, ""); print; next } else exit }' "$0"
}

apply=false
assume_yes=false
for arg in "$@"; do
  case "$arg" in
    --apply) apply=true ;;
    -y | --yes) assume_yes=true ;;
    --repo=*) REPO="${arg#--repo=}" ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$arg' (try --help)" >&2
      exit 2
      ;;
  esac
done

command -v gh >/dev/null 2>&1 || {
  echo "error: gh CLI not found -- install from https://cli.github.com/" >&2
  exit 1
}
command -v jq >/dev/null 2>&1 || {
  echo "error: jq not found -- install jq to run this script" >&2
  exit 1
}
gh auth status >/dev/null 2>&1 || {
  echo "error: gh is not authenticated -- run 'gh auth login'" >&2
  exit 1
}

# Build the jq selector by OR-ing a startswith() clause per prefix. Each prefix
# is JSON-encoded via jq so any quotes/backslashes are escaped safely.
select_expr=""
for p in "${PREFIXES[@]}"; do
  enc=$(jq -cn --arg s "$p" '$s')
  select_expr+="${select_expr:+ or }(.body | startswith($enc))"
done
match_filter="select(.body != null and ($select_expr))"

echo "Repository : $REPO"
echo "Matching   : body starts with one of:"
for p in "${PREFIXES[@]}"; do echo "               - \"$p\""; done
echo "Tags        : preserved (releases deleted without --cleanup-tag)"
echo

# Discover matching releases across all pages. gh applies --jq per page when
# paginating, so this streams one "<tag>\t<first body line>" row per match.
echo "Fetching releases for $REPO ..." >&2
if ! rows_raw=$(gh api "repos/$REPO/releases" --paginate \
  --jq "[.[] | $match_filter] | .[] | [.tag_name, (.body | split(\"\n\")[0] | rtrimstr(\"\r\"))] | @tsv"); then
  echo "error: failed to list releases for $REPO" >&2
  exit 1
fi

tags=()
if [[ -n "$rows_raw" ]]; then
  while IFS=$'\t' read -r tag firstline; do
    [[ -z "$tag" ]] && continue
    tags+=("$tag")
    printf '  %-42s %s\n' "$tag" "$firstline"
  done <<<"$rows_raw"
fi

count=${#tags[@]}
echo
echo "Found $count matching release(s)."

if [[ "$count" -eq 0 ]]; then
  echo "Nothing to do."
  exit 0
fi

if [[ "$apply" != true ]]; then
  echo
  echo "Dry run -- no releases were deleted. Re-run with --apply to delete them."
  exit 0
fi

# Back up the full matching release objects before deleting, so the entries can
# be inspected (or recreated) later. --paginate emits one array per page; merge
# them with a local 'jq -s add'.
backup="automated-releases-backup-${REPO//\//-}.json"
echo
echo "Backing up matching releases to $backup ..."
gh api "repos/$REPO/releases" --paginate --jq "[.[] | $match_filter]" | jq -s 'add' >"$backup"

if [[ "$assume_yes" != true ]]; then
  echo
  read -r -p "Delete these $count release(s) from $REPO (tags will be kept)? [y/N] " reply
  case "$reply" in
    [yY] | [yY][eE][sS]) ;;
    *)
      echo "Aborted. No releases deleted."
      exit 0
      ;;
  esac
fi

echo
deleted=0
failed=0
for tag in "${tags[@]}"; do
  # No --cleanup-tag: the Release is removed but the git tag is kept.
  if gh release delete "$tag" --repo "$REPO" --yes; then
    echo "  deleted release: $tag (tag kept)"
    deleted=$((deleted + 1))
  else
    echo "  FAILED to delete: $tag" >&2
    failed=$((failed + 1))
  fi
done

echo
echo "Done. Deleted $deleted release(s); $failed failure(s). Tags were not touched."
[[ "$failed" -eq 0 ]]
