#!/usr/bin/env bash
# usage: run.sh <venv> <app entv|entr|corev|aggrid_min> <mode prod|dev> <port> <out-name> [driver-args...] [-- EXTRA_ENV=...]
# One run = copy-once run dir runs/<app>_<venv-without-dashes> (sources refreshed from src/ every time, .web kept),
# start (bin/start.sh), drive (drivers/drive.py or the explorer probe for aggrid_min), stop (bin/stop.sh).
# prod: single port <port>; dev: frontend <port>, backend <port>+5000.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a5_upgrade_ent/ent/grid
VENV=$1; APP=$2; MODE=$3; P=$4; OUT=$5; shift 5
DARGS=(); EXTRA=()
while [ $# -gt 0 ]; do if [ "$1" = "--" ]; then shift; EXTRA=("$@"); break; fi; DARGS+=("$1"); shift; done
RUN=$W/runs/${APP}_${VENV//-/}${RUNSUFFIX:-}
mkdir -p $RUN
( cd $W/src/$APP && tar --exclude=.web --exclude=__pycache__ -cf - . ) | ( cd $RUN && tar -xf - )
[ -d $RUN/$APP ] && [ -f $W/src/probe.py ] && [ "$APP" != aggrid_min ] && cp $W/src/probe.py $RUN/$APP/probe.py
if [ "$MODE" = prod ]; then FP=$P; BP=$P; else FP=$P; BP=$((P+5000)); fi
cd $W
bin/start.sh $VENV $RUN $W/logs/$OUT.log $MODE $FP $BP "${EXTRA[@]}" || { bin/stop.sh; exit 1; }
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
if [ "$APP" = aggrid_min ]; then
  $SB/envs/driver/bin/python scripts/probe_aggrid_min.py http://localhost:$FP out/$OUT $VENV $OUT > out/$OUT.txt 2>&1
else
  BPARG=(); [ "$MODE" = dev ] && BPARG=(--backend-port $BP)
  $SB/envs/driver/bin/python drivers/drive.py --app $APP --url http://localhost:$FP "${BPARG[@]}" --out out/$OUT --server-venv $VENV "${DARGS[@]}" > out/$OUT.txt 2>&1
fi
echo "driver exit=$?"
bin/stop.sh
