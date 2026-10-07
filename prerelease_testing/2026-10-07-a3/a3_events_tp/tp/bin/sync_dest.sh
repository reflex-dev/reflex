#!/bin/bash
# Usage: sync_dest.sh <subdir> [<subdir>...]  -- copy subdirs of the work dir into DEST, excluding build outputs (no rsync here)
SB=${SB:-/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad}
W=$SB/apps/a3_events_tp/tp
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/tp
mkdir -p "$DEST"
for d in "$@"; do
  mkdir -p "$DEST/$d"
  if [ -d "$W/$d" ]; then
    (cd "$W" && tar cf - --exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ --exclude='*.pyc' --exclude=.venv --exclude=.git "$d") | (cd "$DEST" && tar xf -)
  else
    cp "$W/$d" "$DEST/$d"
  fi
done
