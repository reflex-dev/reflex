#!/bin/bash
# killtree.sh <pidfile>: TERM the process in the pid file and all of its descendants (no name matching).
pid=$(cat "$1" 2>/dev/null) || exit 0
descendants() { for c in $(pgrep -P "$1"); do descendants "$c"; echo "$c"; done; }
for p in $(descendants "$pid") "$pid"; do kill "$p" 2>/dev/null; done
sleep 3
for p in $(descendants "$pid") "$pid"; do kill -9 "$p" 2>/dev/null; done
