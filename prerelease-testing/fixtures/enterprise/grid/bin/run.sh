#!/usr/bin/env bash
# usage: run.sh <venv> <app entv|entr|corev|aggrid_min> <mode prod|dev> <port> <out-name> [driver-args...] [-- EXTRA_ENV=...]
# One run = run dir $WORK/grid/runs/<app>_<venv-without-dashes>[$RUNSUFFIX] (sources refreshed from src/ every time, .web kept),
# start (bin/start.sh), drive (drivers/drive.py, or scripts/probe_aggrid_min.py for aggrid_min), stop (bin/stop.sh).
# prod: single port <port>; dev: frontend <port>, backend <port>+5000. Outputs: $WORK/grid/out/<out-name>{.txt,/}.
set -u
. "$(dirname "$0")/../../lib.sh"; fx_sync grid; W=$WORK/grid; B=$FX/grid/bin
VENV=$1; APP=$2; MODE=$3; P=$4; OUT=$5; shift 5
DARGS=(); EXTRA=()
while [ $# -gt 0 ]; do if [ "$1" = "--" ]; then shift; EXTRA=("$@"); break; fi; DARGS+=("$1"); shift; done
RUN=$W/runs/${APP}_${VENV//-/}${RUNSUFFIX:-}
mkdir -p "$RUN"
( cd "$FX/grid/src/$APP" && tar --exclude=.web --exclude=__pycache__ -cf - . ) | ( cd "$RUN" && tar -xf - )
[ -d "$RUN/$APP" ] && [ "$APP" != aggrid_min ] && cp "$FX/grid/src/probe.py" "$RUN/$APP/probe.py"
if [ "$MODE" = prod ]; then FP=$P; BP=$P; else FP=$P; BP=$((P+5000)); fi
cd "$W"
"$B/start.sh" "$VENV" "$RUN" "$W/logs/$OUT.log" "$MODE" $FP $BP "${EXTRA[@]}" || { "$B/stop.sh"; exit 1; }
if [ "$APP" = aggrid_min ]; then
  $NP "$DRVPY" scripts/probe_aggrid_min.py http://localhost:$FP out/$OUT "$VENV" "$OUT" > out/$OUT.txt 2>&1
else
  BPARG=(); [ "$MODE" = dev ] && BPARG=(--backend-port $BP)
  $NP "$DRVPY" drivers/drive.py --app "$APP" --url http://localhost:$FP "${BPARG[@]}" --out out/$OUT --server-venv "$VENV" "${DARGS[@]}" > out/$OUT.txt 2>&1
fi
echo "driver exit=$?"
"$B/stop.sh"
