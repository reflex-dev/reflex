#!/bin/bash
# Kill everything this cluster starts on its reserved ports (5580 frontend / 9980 backend).
# NOTE: never plain `pkill -f` here - the pattern also matches the calling shell's own
# command line (which contains this script's text), which kills the test driver itself.
ancestors=" "
pid=$$
while [ "$pid" != "1" ] && [ -n "$pid" ]; do
  ancestors="$ancestors$pid "
  pid=$(awk '{print $4}' /proc/$pid/stat 2>/dev/null)
done
kill_match() {
  for p in $(pgrep -f "$1" 2>/dev/null); do
    case "$ancestors" in *" $p "*) continue;; esac
    kill -9 "$p" 2>/dev/null
  done
}
kill_match "reflex run --frontend-port 5580"
kill_match "react-router dev"
kill_match "bun run dev"
sleep 1
for port in 5580 9980; do
  hexport=$(printf '%04X' "$port")
  for ino in $(awk -v p=":$hexport" 'NR>1 && $2 ~ p"$" {print $10}' /proc/net/tcp); do
    hpid=$(grep -l "socket:\[$ino\]" /proc/*/fd/* 2>/dev/null | head -1 | cut -d/ -f3)
    case "$ancestors" in *" $hpid "*) continue;; esac
    [ -n "$hpid" ] && kill -9 "$hpid" 2>/dev/null
  done
done
sleep 1
exit 0
