#!/usr/bin/env bash
# Usage: post_sync.sh <base_url> <N> <outfile>
# POSTs /_reflex/cookies/sync N times (new connection each) and tabulates status per worker pid
# (pid from the x-worker-pid header that the verifier app adds when VAUTH_PID_HEADER=1).
BASE=$1; N=$2; OUT=$3; : > $OUT
for i in $(seq $N); do
  hdr=$(curl -s --noproxy '*' -o /dev/null -D - -X POST "$BASE/_reflex/cookies/sync" -H 'Content-Type: application/json' -d '{}')
  code=$(echo "$hdr" | head -1 | awk '{print $2}')
  pid=$(echo "$hdr" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-worker-pid"{print $2}')
  echo "$i $code ${pid:-nopid}" >> $OUT
done
echo "status counts:"; awk '{print $2}' $OUT | sort | uniq -c
echo "per worker pid (pid: statuses):"; awk '{a[$3]=a[$3]" "$2} END {for (p in a) print "  "p":"a[p]}' $OUT | sort
