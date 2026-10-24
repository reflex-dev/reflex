#!/usr/bin/env bash
# #7566: does a `.web` created by 0.10.0 get migrated by 0.10.1a1, and does a SOURCE-ONLY hot reload reinstall frontend
# packages? Matrix over the package manager (bun = default, npm = REFLEX_USE_NPM=1):
#   1. blank app, prev venv (0.10.0): `reflex run` (ports FP/BP) -> up -> touch the app module (source-only change) -> wait
#      -> count "Installing frontend packages|development dependencies" blocks after the reload -> stop. Snapshot package.json.
#   2. same app dir + .web, new venv (0.10.1a1): run -> hot reload -> count again -> stop. Snapshot package.json.
#   3. cold: rm -rf .web -> new venv: run -> hot reload -> count -> stop.
# Usage: hotreload_devdeps.sh [bun|npm ...]   (default both). Ports FP=3480 BP=8480. Output: $X/logs/*, summary on stdout.
set -u
: "${SB:?}"
X=$SB/apps/upgrade_packaging/hotreload; mkdir -p "$X/logs"; cd "$SB"
FP=${FP:-3480}; BP=${BP:-8480}
export REFLEX_TELEMETRY_ENABLED=false
NEWV=$SB/envs/new; PREVV=$SB/envs/upgrade_packaging-pure-prev
http() { curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "$1"; }
start() { # start <venv> <appdir> <log>
  (cd "$2" && setsid "$1/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > "$3" 2>&1 < /dev/null &) ; sleep 2
  local t0=$(date +%s)
  while true; do
    [ "$(http http://localhost:$FP/)" = 200 ] && [ "$(http http://localhost:$BP/ping)" = 200 ] && { echo "up after $(( $(date +%s) - t0 ))s"; return 0; }
    [ $(( $(date +%s) - t0 )) -gt 420 ] && { echo "TIMEOUT"; tail -20 "$3"; return 1; }
    sleep 3
  done
}
stop() { # stop: kill everything listening on FP/BP and the reflex main process
  for p in $FP $BP; do for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do kill -TERM "$pid" 2>/dev/null; done; done
  pkill -TERM -f "reflex run --frontend-port $FP " 2>/dev/null; sleep 4
  for p in $FP $BP; do for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do kill -KILL "$pid" 2>/dev/null; done; done
}
installs() { grep -cE "Installing frontend packages|Installing frontend development dependencies|Applying frontend package overrides" "$1"; }
phase() { # phase <label> <venv> <appdir>
  local lab=$1 v=$2 d=$3 log=$X/logs/$1.server.log
  echo "--- $lab ($(basename "$v"))"; start "$v" "$d" "$log" || { stop; return 1; }
  local n0; n0=$(installs "$log"); echo "  installs during startup: $n0"
  sed -i 's/Welcome to Reflex!/Welcome to Reflex!!/' "$d/blankapp/blankapp.py"; sleep 12   # source-only change -> hot reload
  local n1; n1=$(installs "$log"); echo "  installs after a source-only hot reload: $(( n1 - n0 )) (reload lines: $(grep -ciE 'reload|Compiling' "$log"))"
  touch "$d/blankapp/blankapp.py"; sleep 10; echo "  installs after a second reload (touch): $(( $(installs "$log") - n1 ))"
  echo "  frontend still 200: $(http http://localhost:$FP/)"; stop
  cp "$d/.web/package.json" "$X/logs/$lab.package.json"
  "$SB/envs/driver/bin/python" -I -c "import json,sys; d=json.load(open(sys.argv[1])); print('  deps:', len(d.get('dependencies',{})), 'devDeps:', sorted(d.get('devDependencies',{}).keys()))" "$d/.web/package.json"
}
for pm in ${@:-bun npm}; do
  echo "=== package manager: $pm"
  if [ $pm = npm ]; then export REFLEX_USE_NPM=1; else unset REFLEX_USE_NPM; fi
  A=$X/app-$pm; rm -rf "$A"; mkdir -p "$A"; (cd "$A" && "$PREVV/bin/reflex" init --name blankapp --template blank > "$X/logs/$pm-init-prev.log" 2>&1; echo "init (prev) rc=$?")
  phase "$pm-1-prev" "$PREVV" "$A"
  phase "$pm-2-up-inplace" "$NEWV" "$A"
  rm -rf "$A/.web"; phase "$pm-3-cold-new" "$NEWV" "$A"
  diff <("$SB/envs/driver/bin/python" -I -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])),indent=1,sort_keys=True))" "$X/logs/$pm-2-up-inplace.package.json") <("$SB/envs/driver/bin/python" -I -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])),indent=1,sort_keys=True))" "$X/logs/$pm-3-cold-new.package.json") > "$X/logs/$pm-inplace-vs-cold.package.diff"; echo "  in-place vs cold package.json (normalized): $(grep -c '^[<>]' "$X/logs/$pm-inplace-vs-cold.package.diff") differing lines"
  rm -rf "$A/.web"
done
echo "=== done $(date +%T)"
