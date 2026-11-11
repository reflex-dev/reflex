#!/usr/bin/env bash
# usage: cv_case.sh <venv> <appdir> <dev|prod> <port_fe> <port_be> <tag> <CV_CASE> [extra ENV=V ...] -- <paths for cv_drive.py>
OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$OLDSB/p7/work/evt
venv=$1 app=$2 mode=$3 fp=$4 bp=$5 tag=$6 case=$7; shift 7
extra=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do extra+=("$1"); shift; done; shift
SRV_ENV="EXPECT_VENV=$venv CV_CASE=$case ${extra[*]}" bash $W/scripts/srv.sh start "$venv" "$app" "$mode" "$fp" "$bp" "$tag" && \
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $OLDSB/p7/envs/driver/bin/python $W/scripts/cv_drive.py "http://localhost:$fp" "$@"
bash $W/scripts/srv.sh stop "$tag" >/dev/null
