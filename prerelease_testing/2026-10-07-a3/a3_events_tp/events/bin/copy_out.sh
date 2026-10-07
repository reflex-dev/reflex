#!/bin/bash
# Usage: copy_out.sh -- copy suite/mini outputs (reports, txt, png, gzipped ws frames) and logs into DEST.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_events_tp/events
D=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/events
mkdir -p "$D/out" "$D/logs" "$D/prev_out"
cp "$W/out/suite_table.md" "$D/out/" 2>/dev/null
for dir in "$W"/out/*/; do
  n=$(basename "$dir"); mkdir -p "$D/out/$n"
  cp "$dir"/*.json "$dir"/*.txt "$D/out/$n/" 2>/dev/null
  case "$n" in mini_*) cp "$dir"/*a_returns_b_raises.png "$dir"/*gen_yield_then_raise.png "$D/out/$n/" 2>/dev/null;; *) cp "$dir"/*.png "$D/out/$n/" 2>/dev/null;; esac
  for f in "$D/out/$n"/*wsframes.json; do [ -f "$f" ] && gzip -f "$f"; done
done
cp "$W"/logs/*.log "$D/logs/"
# 10-06 baselines reused in the table (0.9.12 nested, a1 dev)
mkdir -p "$D/prev_out/stable_dev" "$D/prev_out/alpha_dev"
cp "$W"/prev_out/stable_dev/*report.json "$D/prev_out/stable_dev/"; cp "$W"/prev_out/*.txt "$D/prev_out/"
cp "$W"/prev_out/alpha_dev/*report.json "$W"/prev_out/alpha_dev/alpha_dev_full.txt "$D/prev_out/alpha_dev/"
du -sh "$D"
