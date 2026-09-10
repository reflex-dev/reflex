#!/bin/bash
# Second pass: fresh frontend compile (no leaked .web/nocompile) for the new ordering checks + aligned interval test.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath; S=$A/scripts
export LOGDIR=logs3
t() { echo; echo "##### $(date +%T) $*"; }
for v in smoke:hotpath_app:3190:8190:smoke2 hp313:hotpath_app_313:3191:8191:hp3132 base0910:hotpath_app_base:3192:8192:base2 hp313_base:hotpath_app_313_base:3193:8193:base3132; do
  IFS=: read venv appdir fp bp label <<< "$v"
  rm -f $A/$appdir/.web/nocompile
  t pass2 $label; $S/run_pw.sh $venv $appdir $fp $bp $label --only ordering,interval,shadow
done
t nocompile repro smoke; $S/repro_nocompile.sh smoke hotpath_app 3194 8194 smoke
t nocompile repro base0910; $S/repro_nocompile.sh base0910 hotpath_app_base 3195 8195 base0910
t gwt disk smoke; $S/repro_gwt_disk.sh smoke hotpath_app 8196 smoke
t gwt disk base0910; $S/repro_gwt_disk.sh base0910 hotpath_app_base 8197 base0910
echo; echo "PASS2 DONE $(date +%T)"
