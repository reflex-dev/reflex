#!/usr/bin/env bash
# usage: own_run.sh <venv> <gridshare|hyd15> <dev|prod> <label>
# gridshare: own/gridshare app on 3611(/8611), driver probes/gridshare_drive.py
# hyd15:     fixture grid/src/entr app in dev on 3612/8612, driver probes/hyd15_drive.py (touches the app module for a hot reload)
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; fx_sync grid; GW=$WORK/grid; B=$F/grid/bin; O=$SB/apps/enterprise/own
V=$1; APP=$2; M=$3; L=$4; mkdir -p "$O/out"
case $APP in
  gridshare) SRC=$O/gridshare; P=3611;;
  hyd15) SRC=$F/grid/src/entr; P=3612;;
esac
RUN=$GW/runs/${APP}_${V//-/}; mkdir -p "$RUN"; (cd "$SRC" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$RUN" && tar -xf -)
[ "$APP" = hyd15 ] && cp "$F/grid/src/probe.py" "$RUN/entr/probe.py"
if [ "$M" = prod ]; then FP=$P; BP=$P; else FP=$P; BP=$((P+5000)); fi
cd "$GW"
"$B/start.sh" "$V" "$RUN" "$GW/logs/$APP-$M-$L.log" "$M" $FP $BP QA_EXPECT_VENV=$V || { "$B/stop.sh"; exit 1; }
cd "$O/probes"
case $APP in
  gridshare) $NP "$DRVPY" gridshare_drive.py http://localhost:$FP $L > "$O/out/gridshare_$L.txt" 2>&1;;
  hyd15) $NP "$DRVPY" hyd15_drive.py http://localhost:$FP $L "$RUN/entr/entr.py" > "$O/out/hyd15_$L.txt" 2>&1;;
esac
echo "driver exit=$?"; grep -E "^\[FAIL\]|^SUMMARY" "$O/out/${APP}_$L.txt" | cut -c1-300
LOGF=$GW/logs/$APP-$M-$L.log
echo "server log: tracebacks=$(grep -c Traceback "$LOGF") errors=$(grep -c -i 'error' "$LOGF") reload=$(grep -ci 'reload' "$LOGF")"
"$B/stop.sh"
