#!/usr/bin/env bash
# Claim a board item: scripts/claim.sh <item> [note]. First push wins.
set -euo pipefail
item="${1:?usage: claim.sh <item> [note]}"; note="${2:-}"
root="$(git rev-parse --show-toplevel)"; cd "$root"
branch="$(git rev-parse --abbrev-ref HEAD)"
board="prerelease_testing/2026-10-07/board"; f="$board/claims/$item.md"
[ -f "$board/items/$item.md" ] || { echo "no such item: $item (see $board/items/)"; exit 2; }
git diff --quiet && git diff --cached --quiet || { echo "commit or stash your changes first (claim needs a clean tree)"; exit 1; }
git pull --rebase -q origin "$branch"
if grep -q 'status: claimed-by-orchestrator' "$board/items/$item.md"; then echo "$item is run by the orchestrating session; pick another"; exit 3; fi
if [ -f "$f" ] && ! grep -qE '^status: (done|abandoned)' "$f"; then echo "already claimed:"; cat "$f"; exit 4; fi
who="${CLAUDE_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-$(hostname)-$$}}"
cat > "$f" <<EOT
item: $item
claimed_by: $who
claimed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
status: in-progress
note: $note
EOT
git add "$f"; git commit -q -m "board: claim $item" -m "Claimed by $who"
if ! git push -q origin HEAD 2>/dev/null; then
  if ! git pull --rebase -q origin "$branch" 2>/dev/null; then git rebase --abort 2>/dev/null || true; git reset -q --hard "origin/$branch"; echo "lost the race (conflicting claim):"; cat "$f" 2>/dev/null; exit 5; fi
  if ! grep -q "claimed_by: $who" "$f"; then git reset -q --hard "origin/$branch"; echo "lost the race:"; cat "$f"; exit 5; fi
  git push -q origin HEAD
fi
echo "claimed $item as $who"
