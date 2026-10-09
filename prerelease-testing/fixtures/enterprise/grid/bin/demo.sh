#!/usr/bin/env bash
# usage: demo.sh <venv> <app dnd|flow|mantine|map|highcharts|tickets|rxeapp> <mode prod|dev> <label>
# Refresh $WORK/grid/runs/<app>_demo_<venv> from $WORK/grid/demos/<app> (bin/fetch_demos.sh; rxeapp is our own src/rxeapp),
# start (prod: port 3608; dev: 3609/8609), run the app's driver (map: smoke_routes over its 4 routes; tickets: + api_tickets.py), stop.
set -u
. "$(dirname "$0")/../../lib.sh"; fx_sync grid; W=$WORK/grid; B=$FX/grid/bin
VENV=$1; APP=$2; MODE=$3; LABEL=$4
SRC=$W/demos/$APP; [ "$APP" = rxeapp ] && SRC=$FX/grid/src/rxeapp
[ -d "$SRC" ] || { echo "no $SRC: run bin/fetch_demos.sh first"; exit 1; }
RUN=$W/runs/${APP}_demo_${VENV//-/}
mkdir -p "$RUN"; ( cd "$SRC" && tar --exclude=.web --exclude=__pycache__ -cf - . ) | ( cd "$RUN" && tar -xf - )
if [ "$MODE" = prod ]; then FP=3608; BP=3608; else FP=3609; BP=8609; fi
cd "$W"
"$B/start.sh" "$VENV" "$RUN" "$W/logs/$APP-$MODE-$LABEL.log" "$MODE" $FP $BP || { "$B/stop.sh"; exit 1; }
O=out/${APP}_${MODE}_$LABEL
case $APP in
  map) $NP "$DRVPY" scripts/smoke_routes.py http://localhost:$FP $O map-smoke "$VENV" / /fly-to-location /map-controls /vector-layers > $O.txt 2>&1 ;;
  tickets) $NP "$DRVPY" scripts/drive_tickets.py http://localhost:$FP $O "$VENV" $MODE-$LABEL http://localhost:$BP > $O.txt 2>&1
           $NP "$DRVPY" scripts/api_tickets.py http://localhost:$BP ${O}_api.json >> $O.txt 2>&1 ;;
  rxeapp) $NP "$DRVPY" scripts/drive_rxeapp.py http://localhost:$FP $O "$VENV" $MODE-$LABEL "${RXEAPP_BADGE:-0}" > $O.txt 2>&1 ;;
  *) $NP "$DRVPY" scripts/drive_$APP.py http://localhost:$FP $O "$VENV" $MODE-$LABEL > $O.txt 2>&1 ;;
esac
echo "driver exit=$? $(grep -c '^\[PASS\]' $O.txt) pass / $(grep -c '^\[FAIL\]' $O.txt) fail"
grep -E '^\[FAIL\]' $O.txt | cut -c1-220
grep -E '"(console_errors|console_warnings|page_errors|failed_requests|http_errors)"' $O.txt | tr -d '\n '; echo
echo "server tracebacks: $(grep -c Traceback "$W/logs/$APP-$MODE-$LABEL.log")"
"$B/stop.sh"
