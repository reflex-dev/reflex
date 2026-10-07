#!/bin/bash
# Usage: sync_dest.sh -- copy sources/scripts/reports/trimmed logs/jpg screenshots of a3_events_tp into the repo DEST.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_events_tp
D=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp
mkdir -p "$D"
EXC="--exclude=.web --exclude=node_modules --exclude=.states --exclude=__pycache__ --exclude=reflex.lock --exclude=*.db --exclude=assets/external --exclude=fuzz.js --exclude=*.png --exclude=*wsframes.json --exclude=run --exclude=pids --exclude=repos --exclude=sdists --exclude=*.pyc"
cp "$W/sync_dest.sh" "$D/"
# events: sources, drivers, tools, bin, probes, reports (json/txt/md), logs (gz if big)
(cd "$W/events" && tar cf - $EXC src driver tools bin probes out 2>/dev/null) | (cd "$D" && mkdir -p events && cd events && tar xf -)
# third-party: apps, drivers, harness, bin, probes, pytest, logs, out
(cd "$W/tp" && tar cf - $EXC apps drivers harness bin probes pytest_probe pytest_downstream cvstore e2e logs out packages.txt 2>/dev/null) | (cd "$D" && mkdir -p tp && cd tp && tar xf -)
# screenshots -> jpg (quality 60, max width 1000)
for png in $(find "$W/events/out" "$W/tp/out" -name '*.png' 2>/dev/null); do
  rel=${png#$W/}; jpg="$D/${rel%.png}.jpg"; mkdir -p "$(dirname "$jpg")"
  [ -f "$jpg" ] || convert "$png" -resize '640x>' -quality 40 "$jpg"
done
# server logs: keep, gzip those over 300 KB
mkdir -p "$D/events/logs" "$D/tp/logs"
for f in "$W"/events/logs/*.log; do [ -f "$f" ] || continue; b=$(basename "$f"); if [ $(stat -c%s "$f") -gt 300000 ]; then gzip -c "$f" > "$D/events/logs/$b.gz"; else cp "$f" "$D/events/logs/"; fi; done
for f in "$W"/events/out/*/*wsframes.json; do [ -f "$f" ] || continue; rel=${f#$W/}; gzip -c "$f" > "$D/$rel.gz"; done
du -sh "$D"
