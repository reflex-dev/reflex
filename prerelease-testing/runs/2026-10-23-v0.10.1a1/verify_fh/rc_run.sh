#!/usr/bin/env bash
# verify_fh / FS-2: generate an app's .web with the React Compiler ON (dev server, 0.10.1a1), count compiled
# components in the modules vite actually serves, run the offline babel audit, stop the server.
#   rc_run.sh <appdir> <label> [venv=new] [fport=3700] [bport=8700]
# Leaves <appdir>/.web in place (delete it when done). Logs: $V/logs/<label>.log, results: $V/results/audit_<label>.txt
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
V=$SB/apps/verify_fh
APP=$1; LABEL=$2; VENV=${3:-new}; FP=${4:-3700}; BP=${5:-8700}
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$VENV REFLEX_REACT_COMPILER=1
nohup "$SB/envs/$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug > "$V/logs/$LABEL.log" 2>&1 &
PID=$!; echo "$PID" > "$V/logs/$LABEL.pid"
echo "started $LABEL pid=$PID"
up=0
for i in $(seq 1 420); do
  if grep -q "App running at" "$V/logs/$LABEL.log" 2>/dev/null; then up=1; break; fi
  if ! kill -0 "$PID" 2>/dev/null; then echo "SERVER EXITED EARLY"; break; fi
  sleep 1
done
if [ "$up" = 1 ]; then
  echo "up after ${i}s"
  # vite transforms a module on first request: fetch every in-scope module and count compiler output
  W=$APP/.web
  # entry.client.embed.js imports a manifest that only exists in embed builds: requesting it from the dev server
  # logs a (harmless, self-inflicted) vite "Failed to resolve import" error, so skip it
  for f in $(cd "$W" && find app app_components utils/components -name '*.jsx' -o -name '*.js' 2>/dev/null | grep -v entry.client.embed.js | sort); do
    out=$(curl -g --noproxy '*' -s "http://localhost:$FP/$f")
    printf "SERVED %-70s bytes=%-7s _c(=%-3s runtime=%s\n" "$f" "${#out}" "$(grep -o '_c(' <<<"$out" | wc -l)" "$(grep -c 'compiler-runtime' <<<"$out")"
  done | tee "$V/results/served_$LABEL.txt" | awk '{c+=substr($4,5)} END{print "SERVED total _c( =", c}'
  (cd "$W" && node "$V/rc_audit.mjs" "$W" --verbose > "$V/results/audit_$LABEL.txt" 2>&1)
  grep -E "^TOTAL|^  [0-9]+ " "$V/results/audit_$LABEL.txt"
else
  echo "NOT UP; log tail:"; tail -20 "$V/logs/$LABEL.log"
fi
pkill -TERM -P "$PID" 2>/dev/null; kill -TERM "$PID" 2>/dev/null
for i in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
kill -0 "$PID" 2>/dev/null && { pkill -KILL -P "$PID" 2>/dev/null; kill -KILL "$PID" 2>/dev/null; }
rm -f "$V/logs/$LABEL.pid"
ss -ltnp 2>/dev/null | grep -E ":($FP|$BP)\b" && echo "WARNING: port still bound" || echo "stopped $LABEL, ports free"
grep -n -i "traceback\|error:" "$V/logs/$LABEL.log" | grep -v "ErrorBoundary\|error_boundary\|errorboundary" | head -5
