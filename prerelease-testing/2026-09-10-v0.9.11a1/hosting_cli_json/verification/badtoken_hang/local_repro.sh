#!/bin/bash
# Rejected-token repro against a LOCAL fake control plane (no external network,
# no egress proxy involved).  usage: local_repro.sh <reflex-bin> <port> <outprefix> [timeout] [extra args...]
BIN="$1"; PORT="$2"; PFX="$3"; T="${4:-30}"; shift 4
cd /tmp || exit 1
FIFO="$(mktemp -u /tmp/never.XXXX)"; mkfifo "$FIFO"; exec 9<> "$FIFO"
s=$(date +%s.%N)
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
REFLEX_TELEMETRY_ENABLED=false NO_COLOR=1 COLUMNS=200 \
REFLEX_CLOUD_BACKEND_URL="http://127.0.0.1:$PORT" REFLEX_CLOUD_URL="http://127.0.0.1:$PORT" \
REFLEX_ACCESS_TOKEN=bogus-token-123 BROWSER=/bin/true \
  timeout "$T" "$BIN" "$@" <&9 > "$PFX.out" 2> "$PFX.err"
rc=$?
e=$(date +%s.%N); exec 9>&-; rm -f "$FIFO"
echo "rc=$rc elapsed=$(echo "$e - $s" | bc) out_bytes=$(wc -c < "$PFX.out") err_bytes=$(wc -c < "$PFX.err")"
