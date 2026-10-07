#!/bin/bash
# verify_upgrade A3-07: GNU `timeout -s INT` (no --foreground signals the child AND its process group) vs --foreground (child only)
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$1; APP=$2; MODE=$3   # MODE: bg | fg
"$SB/envs/$V/bin/python" -I -c "import reflex; assert '/scratchpad/envs/$V/' in reflex.__file__, reflex.__file__"
cd $APP || exit 1; SELF=$$
FG=""; [ "$MODE" = fg ] && FG="--foreground"
T0=$(date +%s.%N)
REFLEX_TELEMETRY_ENABLED=false setsid timeout $FG -k 30 -s INT 12 $SB/envs/$V/bin/reflex run --json --frontend-port 3640 --backend-port 8640 > /dev/null 2>&1 &
TP=$!
wait $TP; RC=$?
T1=$(date +%s.%N)
echo "$V timeout $MODE -s INT 12 (-k 30): exited rc=$RC after $(echo "$T1 - $T0" | bc) s (12 = INT honoured, ~42 = needed the KILL)"
sleep 2
S=""; for d in /proc/[0-9]*; do c=$(readlink $d/cwd 2>/dev/null) || continue; [ "${d#/proc/}" = "$SELF" ] && continue; case "$c" in "$APP"|"$APP"/*) S="$S ${d#/proc/}";; esac; done
echo "  survivors:$S  listening: $(lsof -nP -iTCP:3640 -iTCP:8640 -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')"
for p in $S; do kill -9 $p 2>/dev/null; done
