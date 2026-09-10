#!/bin/bash
# Copy deliverables (no .web/node_modules/.states/venvs) into the repo artifact dir. Plain cp/tar, no git.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
DEST=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/event_hotpath
rm -rf $DEST; mkdir -p $DEST/apps $DEST/scripts $DEST/logs $DEST/logs_prev_attempt
for app in hotpath_app routes_app; do
  tar -C $A --exclude=.web --exclude=node_modules --exclude=.states --exclude='assets/external' --exclude='*.db' \
      --exclude=venv --exclude='*.pyc' --exclude=__pycache__ --exclude=reflex.lock -cf - $app | tar -C $DEST/apps -xf -
done
cp $A/scripts/*.py $A/scripts/*.sh $DEST/scripts/
cp $A/NOTES.md $DEST/
cp $A/logs/names_smoke.json $DEST/logs/
# this attempt's logs: results/console/screenshots per run, bench json + summary, socket json, offline probes, console outputs
cd $A/logs3
for d in pw_hotpath_* pw_routes_*; do mkdir -p $DEST/logs/$d; cp $d/results.json $d/console.json $DEST/logs/$d/ 2>/dev/null; cp $d/*.png $DEST/logs/$d/ 2>/dev/null; cp $d/visits.txt $d/ws_sent.json $DEST/logs/$d/ 2>/dev/null; done
cp ab_*.json ab_summary.md ab_console.out socket_*.json routes_offline_*.jsonl run_all_pw.out run_pass2.out run_ab.out $DEST/logs/ 2>/dev/null
# server logs, trimmed: drop the bun/npm install chatter, keep everything from the app start onwards, cap at 400 lines around interesting bits
for f in hotpath_*.log routes_*.log socket_*.server.log ab_*.server.log nocompile_*.log gwt_disk_*.log; do
  [ -f "$f" ] || continue
  { grep -n -E "Reflex 0\.|App running|Backend running|Traceback|Error|error|Exception|WARN|Warn|warn|destroyed|eager|nocompile|StateManagerDisk|Unexpected exit|Compil" "$f" | grep -v -i "sitemap\|redis_lock\|peer dependency\|Radix Themes\|installed \|isbot\|react-" | head -400; } > $DEST/logs/${f%.log}.trimmed.log
done
# first attempt evidence referenced from NOTES.md
cd $A/logs2
cp probe_names_*.jsonl probe2_*.jsonl hotpath_smoke_dev_stalefrontend.log $DEST/logs_prev_attempt/ 2>/dev/null
grep -n -E "Traceback|Error|StateManagerDisk|_get_was_touched" hotpath_base_gwt_dev.log | head -60 > $DEST/logs_prev_attempt/hotpath_base_gwt_dev.trimmed.log
for d in pw_routes_smoke_prod pw_routes_smoke_prod_fp pw_routes_base_dev pw_hotpath_hp313_factory pw_hotpath_base_gwt; do mkdir -p $DEST/logs_prev_attempt/$d; cp $d/results.json $DEST/logs_prev_attempt/$d/ 2>/dev/null; done
find $DEST -name '*.pyc' -delete
echo "copied: $(find $DEST -type f | wc -l) files, $(du -sh $DEST | cut -f1)"
