#!/usr/bin/env bash
# List TCP listeners on the given ports (default: the whole area range 3460-3519 / 8460-8519) with pid + cmdline.
ports="$*"
[ -z "$ports" ] && ports="$(seq 3460 3519) $(seq 8460 8519)"
found=0
for p in $ports; do
  for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do
    found=1
    echo "port=$p pid=$pid pgid=$(ps -o pgid= -p $pid | tr -d ' ') cmd=$(tr '\0' ' ' < /proc/$pid/cmdline | cut -c1-160)"
  done
done
[ $found = 0 ] && echo "no listeners on: $(echo $ports | wc -w) ports checked"
exit 0
