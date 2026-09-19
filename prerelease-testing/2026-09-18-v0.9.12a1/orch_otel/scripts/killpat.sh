#!/bin/bash
# kill processes matching $1 without matching our own shell
me=$$
for p in $(pgrep -f "$1"); do
  [ "$p" = "$me" ] && continue
  cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)
  case "$cmd" in
    *killpat.sh*) continue;;
    *"snapshot-bash"*) continue;;
  esac
  kill "$p" 2>/dev/null && echo "killed $p: ${cmd:0:90}"
done
