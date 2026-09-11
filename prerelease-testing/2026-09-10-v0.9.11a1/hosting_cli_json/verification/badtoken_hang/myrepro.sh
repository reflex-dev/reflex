#!/bin/bash
# Minimal hand repro, exactly as written in the claim.
# usage: myrepro.sh <reflex-bin> <outprefix> [timeout]
BIN="$1"; PFX="$2"; T="${3:-45}"
cd /tmp || exit 1
FIFO="$(mktemp -u /tmp/never.XXXX)"
mkfifo "$FIFO"
exec 9<> "$FIFO"
start=$(date +%s.%N)
REFLEX_TELEMETRY_ENABLED=false NO_COLOR=1 REFLEX_ACCESS_TOKEN=bogus-token-123 \
  timeout "$T" "$BIN" cloud apps list --json --no-interactive <&9 > "$PFX.out" 2> "$PFX.err"
rc=$?
end=$(date +%s.%N)
exec 9>&-
rm -f "$FIFO"
echo "rc=$rc elapsed=$(echo "$end - $start" | bc)s out_bytes=$(wc -c < "$PFX.out") err_bytes=$(wc -c < "$PFX.err")"
