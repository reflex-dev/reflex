#!/bin/bash
# Usage: copy_dest.sh -- copy sources/scripts (no build output) into the repo DEST dir.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_events_tp/events
D=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/events
mkdir -p "$D"
cd "$W" && tar cf - --exclude=.web --exclude=node_modules --exclude=.states --exclude=__pycache__ \
  --exclude=reflex.lock --exclude='*.db' --exclude=assets/external --exclude=fuzz.js src driver tools bin probes | (cd "$D" && tar xf -)
du -sh "$D"
