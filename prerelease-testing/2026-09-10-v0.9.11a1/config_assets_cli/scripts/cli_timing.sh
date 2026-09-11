#!/bin/bash
# Time reflex CLI subcommand help/version on two venvs. Run from a directory
# that is NOT a reflex project (no rxconfig.py) so no config load happens.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
export REFLEX_TELEMETRY_ENABLED=false
CMDS=("--version" "--help" "run --help" "component --help" "cloud --help" "deploy --help" "export --help" "db --help")
printf "%-22s %14s %14s\n" "command" "0.9.10.post2" "0.9.11a1"
for c in "${CMDS[@]}"; do
  row=""
  for env in base0910 smoke; do
    best=999
    for i in 1 2 3 4 5; do
      s=$( { /usr/bin/time -f "%e" $SB/envs/$env/bin/reflex $c >/dev/null 2>/dev/null; } 2>&1 )
      # /usr/bin/time writes to stderr; capture separately
      :
    done
    # redo properly with python timing
    best=$($SB/envs/driver/bin/python - "$SB/envs/$env/bin/reflex" $c <<'PY'
import subprocess, sys, time, os
exe = sys.argv[1]; args = sys.argv[2:]
env = dict(os.environ); env["REFLEX_TELEMETRY_ENABLED"]="false"
ts=[]
for _ in range(5):
    t=time.perf_counter()
    subprocess.run([exe,*args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd="/tmp")
    ts.append(time.perf_counter()-t)
print(f"{min(ts):.3f}")
PY
)
    row="$row $best"
  done
  printf "%-22s %14s %14s\n" "$c" $row
done
