#!/bin/bash
# Kill every process listening on the given TCP port(s) (reflex wrapper + granian workers).
for port in "$@"; do
  pids=$(lsof -tiTCP:$port -sTCP:LISTEN 2>/dev/null | sort -u | tr '\n' ' ')
  [ -n "$pids" ] && { echo "port $port: killing $pids"; kill $pids 2>/dev/null; }
done
sleep 2
for port in "$@"; do
  pids=$(lsof -tiTCP:$port -sTCP:LISTEN 2>/dev/null | sort -u | tr '\n' ' ')
  [ -n "$pids" ] && { echo "port $port: force killing $pids"; kill -9 $pids 2>/dev/null; }
done
exit 0
