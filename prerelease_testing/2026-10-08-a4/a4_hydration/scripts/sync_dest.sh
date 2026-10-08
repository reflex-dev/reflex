#!/bin/bash
# Copy reusable artifacts (no .web / node_modules / venvs / dbs / run dirs) into the repo DEST (no rsync on this box).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_hydration
DEST=/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_hydration
mkdir -p $DEST/verification $DEST/results $DEST/verification/out
cd $W && tar --exclude=.web --exclude=node_modules --exclude=.states --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ \
  -cf - src drivers scripts cv pr7505 | tar -xf - -C $DEST
cd $W/v && tar --exclude=__pycache__ -cf - src drivers scripts | tar -xf - -C $DEST/verification
cd $W/results && find . -type f ! -name '*.raw.json' ! -name '*.stdout' -size -400k | tar -cf - -T - | tar -xf - -C $DEST/results
cd $W/v/out && find . -maxdepth 1 -type f \( -name '*.json' -o -name '*.txt' \) -size -300k | tar -cf - -T - | tar -xf - -C $DEST/verification/out
du -sh $DEST
