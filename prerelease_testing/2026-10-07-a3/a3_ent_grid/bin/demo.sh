#!/usr/bin/env bash
# usage: demo.sh <venv> <app dnd|flow|mantine|map> <mode prod|dev> <label>
# Refresh runs/<app>_demo_<venv> from src/<app>, start (prod: port 3318; dev: 3319/8319), run the a2-pass driver for the app
# (map: smoke_routes over its 4 routes), stop.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_grid
VENV=$1; APP=$2; MODE=$3; LABEL=$4
RUN=$W/runs/${APP}_demo_${VENV//-/}
mkdir -p $RUN; ( cd $W/src/$APP && tar --exclude=.web --exclude=__pycache__ -cf - . ) | ( cd $RUN && tar -xf - )
if [ "$MODE" = prod ]; then FP=3318; BP=3318; else FP=3319; BP=8319; fi
cd $W
bin/start.sh $VENV $RUN $W/logs/$APP-$MODE-$LABEL.log $MODE $FP $BP || { bin/stop.sh; exit 1; }
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
D=$SB/envs/driver/bin/python
case $APP in
  map) $D scripts/smoke_routes.py http://localhost:$FP out/${APP}_${MODE}_$LABEL map-smoke $VENV / /fly-to-location /map-controls /vector-layers > out/${APP}_${MODE}_$LABEL.txt 2>&1 ;;
  *) $D scripts/drive_$APP.py http://localhost:$FP out/${APP}_${MODE}_$LABEL $VENV $MODE-$LABEL > out/${APP}_${MODE}_$LABEL.txt 2>&1 ;;
esac
echo "driver exit=$? $(grep -c '^\[PASS\]' out/${APP}_${MODE}_$LABEL.txt) pass / $(grep -c '^\[FAIL\]' out/${APP}_${MODE}_$LABEL.txt) fail"
grep -E '^\[FAIL\]' out/${APP}_${MODE}_$LABEL.txt | cut -c1-220
grep -E '"(console_errors|console_warnings|page_errors|failed_requests|http_errors)"' out/${APP}_${MODE}_$LABEL.txt | tr -d '\n '; echo
echo "server tracebacks: $(grep -c Traceback $W/logs/$APP-$MODE-$LABEL.log)"
bin/stop.sh
