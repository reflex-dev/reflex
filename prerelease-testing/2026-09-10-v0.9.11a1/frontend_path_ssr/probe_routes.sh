#!/bin/bash
# probe_routes.sh <port> <prefix>
port=$1; prefix=$2
for u in "$prefix/" "$prefix/about" "$prefix/nosuchroute" /ping; do
  printf "%-24s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$port$u)"
done
