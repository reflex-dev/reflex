#!/bin/bash
# Copy this cluster's artifacts to the repo (no .web/node_modules/venvs/caches/dbs/raw logs). Uses tar (no rsync here).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_class_state
DEST=/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_class_state
rm -rf $DEST; mkdir -p $DEST
cd $W && tar cf - --exclude='.web' --exclude='node_modules' --exclude='.states' --exclude='assets/external' --exclude='*.db' \
  --exclude='reflex.lock' --exclude='__pycache__' --exclude='*.raw.log' --exclude='.pytest_cache' --exclude='*.bin' \
  --exclude='./downstream/unz' --exclude='./run' --exclude='./pids' --exclude='./orig/a3_NOTES.md' --exclude='alembic' --exclude='*.png.full' . \
  | (cd $DEST && tar xf -)
du -sh $DEST
