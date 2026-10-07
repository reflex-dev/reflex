#!/usr/bin/env bash
# Claim a board item: scripts/claim.sh <item> [note]. First push wins.
set -euo pipefail
item="${1:?usage: claim.sh <item> [note]}"; note="${2:-}"
root="$(git rev-parse --show-toplevel)"; cd "$root"
board="prerelease_testing/2026-10-07/board"
[ -f "$board/items/$item.md" ] || { echo "no such item: $item (see $board/items/)"; exit 2; }
grep -q 'status: claimed-by-orchestrator' "$board/items/$item.md" && { echo "$item is run by the orchestrating session; pick another"; exit 3; }
git pull --rebase -q origin "$(git rev-parse --abbrev-ref HEAD)"
if [ -f "$board/claims/$item.md" ] && ! grep -q '^status: done' "$board/claims/$item.md"; then
  echo "already claimed:"; cat "$board/claims/$item.md"; exit 4
fi
who="${CLAUDE_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-$(hostname)-$$}}"
cat > "$board/claims/$item.md" <<EOT
item: $item
claimed_by: $who
claimed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
status: in-progress
note: $note
EOT
git add "$board/claims/$item.md"
git commit -q -m "board: claim $item" -m "Claimed by $who"
if ! git push -q origin HEAD; then
  git pull --rebase -q origin "$(git rev-parse --abbrev-ref HEAD)" || true
  if git log --oneline -3 -- "$board/claims/$item.md" | grep -vq "$(git rev-parse --short HEAD)"; then :; fi
  if [ "$(git log --format=%an -1 -- "$board/claims/$item.md")" != "" ] && ! grep -q "claimed_by: $who" "$board/claims/$item.md"; then
    echo "lost the race: $item was claimed first by:"; cat "$board/claims/$item.md"; git reset -q --hard "origin/$(git rev-parse --abbrev-ref HEAD)"; exit 5
  fi
  git push -q origin HEAD
fi
echo "claimed $item as $who"
