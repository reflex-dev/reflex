#!/bin/bash
# same as local_repro.sh but runs in a given cwd
BIN="$1"; PORT="$2"; PFX="$3"; T="${4:-30}"; CWD="$5"; shift 5
cd "$CWD" || exit 1
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
