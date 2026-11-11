#!/usr/bin/env bash
# Lifespan / api_transformer matrix: lifespan.sh <venv> <mode prod-be|dev-be|prod> <port> <tx variants...>
# For each NA_TX variant: start, curl /ping /api/greet /api2/greet, SIGINT the group, print marks + relevant log lines.
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1 mode=$2 port=$3; shift 3
for tx in "$@"; do
  label=ls_${venv}_${mode}_$tx
  marks=$W/logs/$label.jsonl; : > $marks
  case $mode in
    prod-be) args=(--env prod --backend-only --backend-port $port) ;;
    dev-be) args=(--backend-only --backend-port $port) ;;
    prod) args=(--env prod --frontend-port $port --backend-port $port) ;;
  esac
  curl --noproxy '*' -s -m 1 localhost:$port >/dev/null && { echo "PORT BUSY"; exit 3; }
  NA_TX=$tx NA_LOG=$marks $W/bin/srv.sh start $label $venv netapp "${args[@]}" >/dev/null
  up=yes; LABEL=$label $W/bin/srv.sh wait http://localhost:$port/ping 240 >/dev/null || up=no
  echo "=== $venv $mode NA_TX=$tx up=$up"
  if [ $up = yes ]; then
    for path in /ping /api/greet /api2/greet; do
      echo "  GET $path -> $(curl --noproxy '*' -s -m 5 -w ' [%{http_code}]' localhost:$port$path | cut -c1-160)"
    done
  fi
  sleep 1
  $W/bin/srv.sh stop $label >/dev/null
  echo "  marks: $(jq -r '.evt' $marks | tr '\n' ' ')"
  grep -n -i -E "lifespan|twice|appears|boom|Traceback|Error|startup|shutdown" $W/logs/$label.log | grep -v NA_MARK | cut -c1-220 | head -${LINES_MAX:-12} | sed 's/^/  log: /'
done
