#!/usr/bin/env bash
# End-of-item cleanup: stop every server on the item's ports, delete .web/ node_modules/ run copies and throwaway venvs.
set -u
: "${SB:?}"
W=$SB/apps/upgrade_packaging/upgrade; X=$SB/apps/upgrade_packaging
for p in $(seq 3460 3499) $(seq 8460 8499); do
  for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do echo "killing listener on $p: pid $pid"; kill -TERM "$pid" 2>/dev/null; done
done
sleep 3
for p in $(seq 3460 3499) $(seq 8460 8499); do
  for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do echo "force-killing listener on $p: pid $pid"; kill -KILL "$pid" 2>/dev/null; done
done
redis-cli -p 8499 shutdown nosave >/dev/null 2>&1; redis-cli -p 8469 shutdown nosave >/dev/null 2>&1
# .web / node_modules / run copies
find "$W/up/apps" "$W/tp/run" "$W/smoke/run" "$W/inst/run" "$X/initbun" "$X/mixed/run" "$X/hotreload" -maxdepth 4 -type d \( -name .web -o -name node_modules -o -name .states \) -prune -exec rm -rf {} + 2>/dev/null
rm -rf "$W/tp/run" "$W/smoke/run" "$X/mixed/run" "$X/hotreload/app-bun" "$X/hotreload/app-npm" "$X/initbun"/app-* "$X/initbun"/i[1-4]-* "$X/initbun"/rd-* "$X/sdist/build" "$X/sdist/archives" "$W/up/run"
# throwaway venvs
for v in "$SB"/envs/upgrade_packaging-*; do [ -d "$v" ] && { echo "rm venv $(basename "$v")"; rm -rf "$v"; }; done
bash "$W/bin/ports.sh" $(seq 3460 3499) $(seq 8460 8499)
pgrep -af "upgrade_packaging" | grep -v -E "pgrep|cleanup.sh" | cut -c1-120 || true
df -h "$SB" | tail -1
