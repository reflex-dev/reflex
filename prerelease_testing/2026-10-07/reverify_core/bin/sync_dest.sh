#!/bin/bash
# Copy reusable artifacts from the work dir to DEST (no rsync on this box): tar with excludes.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/reverify_core
DEST=/home/user/reflex/prerelease_testing/2026-10-07/reverify_core
mkdir -p $DEST
cd $W && tar -cf - --exclude='.web' --exclude='node_modules' --exclude='.states' --exclude='__pycache__' \
  --exclude='*.db' --exclude='reflex.lock' --exclude='*.bin' --exclude='assets/external' --exclude='pids' \
  --exclude='alembic' --exclude='alembic.ini' --exclude='*.full.log' "$@" | (cd $DEST && tar -xf -)
du -sh $DEST
