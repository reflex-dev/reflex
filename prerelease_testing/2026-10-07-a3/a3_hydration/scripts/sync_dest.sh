#!/bin/bash
# Copy reusable artifacts to the repo DEST (no git). Excludes build/runtime dirs.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_hydration
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_hydration
mkdir -p $DEST
cd $W
items=""
for d in src drivers scripts probes srv.sh cv/bin cv/drivers results trimmed shots; do [ -e $d ] && items="$items $d"; done
tar -cf - --exclude='.web' --exclude='node_modules' --exclude='.states' --exclude='assets/external' --exclude='*.db' \
  --exclude='reflex.lock' --exclude='__pycache__' --exclude='*.pid' --exclude='*.raw.json' --exclude='*.png' $items | tar -xf - -C $DEST
du -sh $DEST
