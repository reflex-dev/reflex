#!/usr/bin/env bash
# #7453: two concurrent `reflex export` on the SAME app dir (fresh copy of forkapp -> run/export-<venv>).
# Usage: export_concurrent.sh <venv> [label]
# Phase A: export #1 and #2 started 2 s apart, both --frontend-only --env prod; record start/end times, exit codes,
#          `unzip -t` of both zips, whether #2 waited (serialized) or ran in parallel, lock files in REFLEX_DIR/locks.
# Phase B: start export #3, kill -9 it after 6 s (mid-build), then export #4 must proceed (lock released by death) and succeed.
# Phase C: `reflex run --env prod` (full) + export started 2 s later: both should finish / serve; export zip valid.
set -u
: "${SB:?}"; PM=$SB/apps/process_model; venv=$1; label=${2:-export-$venv}
A=$PM/run/$label; rm -rf "$A"; mkdir -p "$PM/run" "$PM/out"
(cd "$PM" && tar cf - --exclude=.web --exclude=__pycache__ --exclude='*.db' --exclude='*.log*' forkapp) | (cd "$PM/run" && tar xf - && mv forkapp "$A")
export REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$venv
LOCKS=$("$SB/envs/$venv/bin/python" -I -c "from reflex_base.environment import environment; print(environment.REFLEX_DIR.get()/'locks')")
RX=$SB/envs/$venv/bin/reflex
ts() { date +%s.%N; }
run_export() { # run_export <n> <extra args>
  local n=$1; shift
  local t0; t0=$(ts)
  (cd "$A" && "$RX" export --frontend-only --env prod --zip-dest-dir "$A/zip$n" --loglevel debug "$@" > "$PM/logs/$label-$n.log" 2>&1); local rc=$?
  echo "export$n rc=$rc start=$(printf '%.1f' "$(echo "$t0 - $T0" | bc)") end=$(printf '%.1f' "$(echo "$(ts) - $T0" | bc)") zip=$(ls "$A/zip$n" 2>/dev/null | tr '\n' ' ')"
}
echo "### $label venv=$venv locks=$LOCKS"
# warm-up export so bun install / first build is not part of the race
T0=$(ts); run_export 0 | sed 's/^/warmup: /'
echo "--- Phase A: two concurrent exports (2 s apart)"
T0=$(ts)
run_export 1 & p1=$!
sleep 2
run_export 2 & p2=$!
wait $p1; wait $p2
for n in 1 2; do z=$(ls "$A/zip$n"/*.zip 2>/dev/null | head -1); if [ -n "$z" ]; then unzip -tq "$z" > /dev/null 2>&1 && echo "zip$n: $(basename "$z") OK $(unzip -l "$z" | tail -1)" || echo "zip$n: $(basename "$z") CORRUPT"; else echo "zip$n: MISSING"; fi; done
grep -h -i "lock\|wait" "$PM/logs/$label-1.log" "$PM/logs/$label-2.log" | grep -v "lockfile\|bun.lock\|reflex.lock\|package-lock" | head -5 | cut -c1-200
echo "--- Phase B: kill -9 an export mid-build, then export again"
T0=$(ts)
(cd "$A" && exec "$RX" export --frontend-only --env prod --zip-dest-dir "$A/zip3" --loglevel debug > "$PM/logs/$label-3.log" 2>&1) & p3=$!
sleep 6; echo "kill -9 export3 pid=$p3 at $(printf '%.1f' "$(echo "$(ts) - $T0" | bc)")s (children: $(pgrep -P $p3 | tr '\n' ' '))"; pkill -9 -P $p3; kill -9 $p3 2>/dev/null; wait $p3 2>/dev/null
sleep 1; echo "leftover processes with cwd $A: $(for p in $(pgrep -f "$A"); do echo -n "$p "; done)"; pkill -9 -f "$A" 2>/dev/null
echo "lock files now: $(ls "$LOCKS" 2>/dev/null | wc -l); any flock holder? $(lsof +D "$LOCKS" 2>/dev/null | grep -c lock)"
run_export 4
z=$(ls "$A/zip4"/*.zip 2>/dev/null | head -1); [ -n "$z" ] && (unzip -tq "$z" >/dev/null 2>&1 && echo "zip4 OK" || echo "zip4 CORRUPT") || echo "zip4 MISSING"
echo "--- Phase C: reflex run --env prod + export 2 s later"
T0=$(ts)
(cd "$A" && exec env REFLEX_API_URL=http://localhost:8203 "$RX" run --env prod --frontend-port 8203 --backend-port 8203 --loglevel debug > "$PM/logs/$label-run.log" 2>&1) & prun=$!
sleep 2
run_export 5
for i in $(seq 1 120); do [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8203/ping)" = 200 ] && break; sleep 1; done
echo "run up at $(printf '%.1f' "$(echo "$(ts) - $T0" | bc)")s: index $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8203/) ping $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8203/ping)"
z=$(ls "$A/zip5"/*.zip 2>/dev/null | head -1); [ -n "$z" ] && (unzip -tq "$z" >/dev/null 2>&1 && echo "zip5 OK $(unzip -l "$z" | tail -1)" || echo "zip5 CORRUPT") || echo "zip5 MISSING"
# does the served index reference assets that exist (i.e. not clobbered by the export)?
idx=$(curl -s --noproxy '*' http://localhost:8203/ | grep -o 'assets/[A-Za-z0-9_.-]*\.js' | head -3)
for a in $idx; do echo "asset $a -> $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8203/$a)"; done
kill -TERM $prun; for i in $(seq 1 30); do kill -0 $prun 2>/dev/null || break; sleep 0.5; done; kill -0 $prun 2>/dev/null && { echo "run STILL ALIVE"; pkill -9 -P $prun; kill -9 $prun; } || echo "run exited"
grep -c "Traceback" "$PM/logs/$label-run.log" "$PM/logs/$label-5.log"
