#!/bin/bash
# usage: case_matrix.sh <reflex-bin> <port> <label> <timeout>
BIN="$1"; PORT="$2"; LBL="$3"; T="${4:-25}"
OUT="$(dirname "$0")/out"
run() {
  local name="$1"; shift
  local usetok="$1"; shift
  cd /tmp || return
  local FIFO; FIFO="$(mktemp -u /tmp/never.XXXX)"; mkfifo "$FIFO"; exec 9<> "$FIFO"
  local s; s=$(date +%s.%N)
  if [ "$usetok" = env ]; then
    NO_PROXY=localhost,127.0.0.1 REFLEX_TELEMETRY_ENABLED=false NO_COLOR=1 COLUMNS=200 \
    REFLEX_CLOUD_BACKEND_URL="http://127.0.0.1:$PORT" REFLEX_CLOUD_URL="http://127.0.0.1:$PORT" \
    REFLEX_ACCESS_TOKEN=bogus-token-123 BROWSER=/bin/true \
      timeout "$T" "$BIN" "$@" <&9 > "$OUT/${LBL}_${name}.out" 2> "$OUT/${LBL}_${name}.err"
  else
    NO_PROXY=localhost,127.0.0.1 REFLEX_TELEMETRY_ENABLED=false NO_COLOR=1 COLUMNS=200 \
    REFLEX_CLOUD_BACKEND_URL="http://127.0.0.1:$PORT" REFLEX_CLOUD_URL="http://127.0.0.1:$PORT" \
    BROWSER=/bin/true \
      timeout "$T" "$BIN" "$@" <&9 > "$OUT/${LBL}_${name}.out" 2> "$OUT/${LBL}_${name}.err"
  fi
  local rc=$?
  local e; e=$(date +%s.%N); exec 9>&-; rm -f "$FIFO"
  printf '%-28s rc=%-4s %6.1fs out=%-5s err=%-5s prompted=%s\n' "$name" "$rc" \
    "$(echo "$e - $s"|bc)" "$(wc -c < "$OUT/${LBL}_${name}.out")" "$(wc -c < "$OUT/${LBL}_${name}.err")" \
    "$(grep -qs "hit 'Enter'" "$OUT/${LBL}_${name}.out" "$OUT/${LBL}_${name}.err" && echo yes || echo no)"
}
run no_token_nointeractive none cloud apps list --json --no-interactive
run tokopt_json none cloud apps list --json --token bogus-token-123
run tokopt_json_nointeractive none cloud apps list --json --no-interactive --token bogus-token-123
run env_json_nointeractive env cloud apps list --json --no-interactive
run env_plain env cloud apps list
run env_whoami_json env cloud whoami --json
run env_project_list env cloud project list --json --no-interactive
run env_secrets_list env cloud secrets list --json --no-interactive
