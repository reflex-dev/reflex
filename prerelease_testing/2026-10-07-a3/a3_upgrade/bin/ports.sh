#!/usr/bin/env bash
# List TCP listeners on the given ports (or the whole reserved range) with pid + cmdline.
ports="$*"
[ -z "$ports" ] && ports="$(seq 3200 3239) $(seq 8200 8239)"
found=0
for p in $ports; do
  for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do
    found=1
    echo "port=$p pid=$pid pgid=$(ps -o pgid= -p $pid | tr -d ' ') cmd=$(tr '\0' ' ' < /proc/$pid/cmdline | cut -c1-160)"
  done
done
[ $found = 0 ] && echo "no listeners on: $(echo $ports | wc -w) ports checked"
exit 0
