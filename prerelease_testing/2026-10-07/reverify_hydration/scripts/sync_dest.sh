#!/bin/bash
# Copy reusable artifacts to the repo DEST (no git). Excludes build/runtime dirs.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/reverify_hydration
DEST=/home/user/reflex/prerelease_testing/2026-10-07/reverify_hydration
mkdir -p $DEST
cd $W
items=""
for d in src drivers scripts cv/bin cv/drivers results trimmed shots NOTES.md; do [ -e $d ] && items="$items $d"; done
tar -cf - --exclude='.web' --exclude='node_modules' --exclude='.states' --exclude='assets/external' --exclude='*.db' \
  --exclude='reflex.lock' --exclude='__pycache__' --exclude='*.pid' --exclude='*.raw.json' $items | tar -xf - -C $DEST
du -sh $DEST
