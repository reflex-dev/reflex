#!/bin/bash
# Copy this item's artifacts (scripts, app sources, trimmed logs, outputs) to the repo DEST, without heavy/generated dirs.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_class_state
mkdir -p $DEST
tar -C $W \
  --exclude='.web' --exclude='node_modules' --exclude='.states' --exclude='assets/external' --exclude='*.db' \
  --exclude='reflex.lock' --exclude='__pycache__' --exclude='.venv' --exclude='./pids' --exclude='./src_a3' --exclude='./orig' \
  --exclude='*.full.log' --exclude='./run' --exclude='*.bin' --exclude='*.pkl' --exclude='.pytest_cache' --exclude='./logs/venv' \
  --exclude='*.raw.log' -cf - . | tar -C $DEST -xf -
du -sh $DEST
