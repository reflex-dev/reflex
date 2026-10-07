#!/usr/bin/env bash
# usage: stopsrv.sh <venv path fragment> [app dir fragment]
# SIGINT the `reflex run` of that venv, wait up to 30 s, SIGKILL if still there, then kill orphaned
# react-router dev servers whose command line contains the app dir fragment. Prints what happened.
pat=$1; app=${2:-}
pkill -INT -f "$pat/bin/reflex run"
for i in $(seq 1 30); do pgrep -f "$pat/bin/reflex run" >/dev/null || { echo "reflex stopped after ${i}s on SIGINT"; break; }; sleep 1; done
if pgrep -f "$pat/bin/reflex run" >/dev/null; then echo "reflex still running after 30s of SIGINT; SIGKILL"; pkill -KILL -f "$pat/bin/reflex run"; fi
if [ -n "$app" ]; then
  sleep 1
  if pgrep -f "react-router.*$app" >/dev/null; then echo "orphaned react-router for $app -> kill"; pkill -f "react-router.*$app"; fi
fi
