#!/bin/bash
# Copy reusable artifacts (no .web / node_modules / venvs / dbs / run dirs) into the repo DEST (no rsync on this box).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
DEST=/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_hydration_router
mkdir -p $DEST/results $DEST/trimmed
cd $W && tar --exclude=.web --exclude=node_modules --exclude=.states --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ \
  -cf - src drivers scripts cv | tar -xf - -C $DEST
# keep result files under 400k; frame dumps gzipped
cd $W/results && find . -type f ! -name '*.frames.jsonl' -size -400k | tar -cf - -T - | tar -xf - -C $DEST/results
cd $W/results && for f in $(find . -name '*.frames.jsonl'); do mkdir -p $DEST/results/$(dirname $f); gzip -c $f > $DEST/results/$f.gz; done
[ -d $W/trimmed ] && cp $W/trimmed/* $DEST/trimmed/ 2>/dev/null
du -sh $DEST
