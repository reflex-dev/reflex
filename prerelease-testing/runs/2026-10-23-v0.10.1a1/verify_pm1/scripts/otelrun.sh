#!/usr/bin/env bash
# otelrun.sh <venv> <label> <port> [env assignments...]: backend-only prod otelapp, sample_otel, then count exporter lines per pid.
set -u; : "${SB:?}"; V=$SB/apps/verify_pm1; cd "$V" || exit 2
venv=$1; label=$2; port=$3; shift 3
for kv in "$@"; do export "$kv"; done
export REFLEX_REDIS_URL=${REFLEX_REDIS_URL:-redis://localhost:8739} REFLEX_TELEMETRY_ENABLED=false OTELAPP_OUT=$V/out/otel-$label
rm -rf "$OTELAPP_OUT"
./scripts/serve.sh start "$venv" "$V/otelapp" "$label" prod-be "$port" > /dev/null
pid=$(cat "run/$label.pid"); up=$(./scripts/serve.sh wait "http://localhost:$port/ping" 180)
echo "## $label venv=$venv port=$port env=[$*] $up"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 "$SB/envs/driver/bin/python" -I scripts/sample_otel.py "http://localhost:$port" 40 --json "out/otel-$label.json"
sleep 2
echo "spans.log by pid:"; grep -o 'pid=[0-9]*' "$OTELAPP_OUT/spans.log" 2>/dev/null | sort | uniq -c | tr '\n' ' '; echo
echo "span names:"; grep -o 'name=.*' "$OTELAPP_OUT/spans.log" 2>/dev/null | sort | uniq -c | tr '\n' ' '; echo
echo "metrics.log by pid:"; grep -o 'pid=[0-9]*' "$OTELAPP_OUT/metrics.log" 2>/dev/null | sort | uniq -c | tr '\n' ' '; echo
echo "queued.log lines: $(wc -l < "$OTELAPP_OUT/queued.log") / direct.log lines: $(wc -l < "$OTELAPP_OUT/direct.log")"
./scripts/serve.sh stop "$label" TERM
echo "log: tracebacks=$(grep -c Traceback logs/$label.log) errors=$(grep -c -i 'error' logs/$label.log)"
grep -n -i "traceback\|exception\|error" logs/$label.log | grep -v "errorBound\|_error\|error-boundary" | head -5 | cut -c1-200
