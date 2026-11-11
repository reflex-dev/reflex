#!/bin/bash
# wait.sh <url> [secs]
for i in $(seq 1 ${2:-360}); do c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' $1); [ "$c" = 200 ] && { echo up after ${i}s; exit 0; }; sleep 1; done; echo TIMEOUT; exit 1
