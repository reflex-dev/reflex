#!/bin/bash
# Probe HTTP status + a couple of body markers for a list of routes.
# usage: probe_status.sh <base_url> <out_json> <route>...
set -u
BASE=$1; OUT=$2; shift 2
echo "[" > "$OUT"
first=1
for r in "$@"; do
  hdr=$(curl -s -D - -o /tmp/body.$$ -w '' --noproxy '*' "$BASE$r")
  code=$(printf '%s' "$hdr" | head -1 | awk '{print $2}')
  loc=$(printf '%s' "$hdr" | grep -i '^location:' | tr -d '\r' | sed 's/^[Ll]ocation: *//')
  bytes=$(wc -c < /tmp/body.$$ | tr -d ' ')
  has_root=$(grep -c 'id="root"\|<div id="root"' /tmp/body.$$ || true)
  title=$(grep -o '<title>[^<]*</title>' /tmp/body.$$ | head -1)
  [ $first -eq 0 ] && echo "," >> "$OUT"; first=0
  printf '  {"route": "%s", "status": "%s", "location": "%s", "bytes": %s, "title": "%s"}' \
     "$r" "$code" "$loc" "$bytes" "$(printf '%s' "$title" | sed 's/"/\\"/g')" >> "$OUT"
  printf '%-28s %s  bytes=%-8s %s %s\n' "$r" "$code" "$bytes" "$title" "$loc"
  rm -f /tmp/body.$$
done
echo "" >> "$OUT"; echo "]" >> "$OUT"
