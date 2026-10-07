#!/usr/bin/env bash
# Release a board item: scripts/release.sh <item> done|blocked|abandoned [note]
set -euo pipefail
item="${1:?usage: release.sh <item> done|blocked|abandoned [note]}"; st="${2:?status}"; note="${3:-}"
root="$(git rev-parse --show-toplevel)"; cd "$root"
f="prerelease_testing/2026-10-07/board/claims/$item.md"
[ -f "$f" ] || { echo "no claim file for $item"; exit 2; }
sed -i "s/^status: .*/status: $st/" "$f"; printf 'released_at: %s\nrelease_note: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$note" >> "$f"
git add "$f"; git commit -q -m "board: $item -> $st"; git pull --rebase -q origin "$(git rev-parse --abbrev-ref HEAD)"; git push -q origin HEAD; echo "$item -> $st"
