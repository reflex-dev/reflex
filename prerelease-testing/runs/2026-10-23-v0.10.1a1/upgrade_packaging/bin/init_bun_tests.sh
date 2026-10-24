#!/usr/bin/env bash
# #7639 Bun 1.4.4 and #7556 `reflex init` checks (no servers; `reflex init` installs bun + the frontend packages).
#   B1 fresh REFLEX_DIR, new  -> which bun version is downloaded
#   B2 fresh REFLEX_DIR, prev -> 1.4.2 installed; then new on the SAME dir -> upgraded to 1.4.4?
#   B3 REFLEX_USE_SYSTEM_BUN=1 with the system bun 1.4.2 on PATH: new warning text (prev: no warning, MIN 1.4.0)
#   I1 fresh `reflex init` in a directory named `reflex` (new / prev)        -> expected: refused (reserved name) on both
#   I2 `reflex init --name myapp` in a dir named `reflex`, then re-init without --name (new / prev)  -> #7556
#   I3 re-init of an existing app in a normal dir: tree unchanged?
#   I4 `reflex init --template <bogus>` lists the templates; `reflex --version`; `reflex export` of the blank app (new / prev)
set -u
: "${SB:?}"
X=$SB/apps/upgrade_packaging/initbun; rm -rf "$X"; mkdir -p "$X/logs"; cd "$X"
export REFLEX_TELEMETRY_ENABLED=false
NEWR=$SB/envs/new/bin/reflex; PREVR=$SB/envs/upgrade_packaging-pure-prev/bin/reflex
SYSBUN=$(command -v bun); echo "system bun on PATH: $SYSBUN $($SYSBUN --version); managed default: $(/root/.local/share/reflex/bun/bin/bun --version 2>/dev/null)"
bunv() { "$1/bun/bin/bun" --version 2>/dev/null || echo none; }
run_init() { # run_init <label> <reflex bin> <appdir> [args...]
  local lab=$1 r=$2 d=$3; shift 3; mkdir -p "$d"
  (cd "$d" && "$r" init "$@" > "$X/logs/$lab.log" 2>&1; echo "rc=$?") | tr -d '\n'
  echo " [$lab] bun lines: $(grep -iE 'bun' "$X/logs/$lab.log" | grep -v 'bunfig' | cut -c1-160 | tr '\n' '|')"
}
echo "=== B1 fresh REFLEX_DIR, new"; export REFLEX_DIR=$X/rd-fresh; run_init b1-new "$NEWR" "$X/app-b1" --template blank; echo "  bun in rd-fresh: $(bunv "$REFLEX_DIR")"
echo "=== B2 fresh REFLEX_DIR, prev then new"; export REFLEX_DIR=$X/rd-upg; run_init b2-prev "$PREVR" "$X/app-b2" --template blank; echo "  bun after prev: $(bunv "$REFLEX_DIR")"
run_init b2-new "$NEWR" "$X/app-b2"; echo "  bun after new re-init on the same REFLEX_DIR: $(bunv "$REFLEX_DIR")"
echo "=== B3 REFLEX_USE_SYSTEM_BUN=1 (system bun $($SYSBUN --version))"; export REFLEX_DIR=$X/rd-sys
REFLEX_USE_SYSTEM_BUN=1 run_init b3-new "$NEWR" "$X/app-b3" --template blank; echo "  warning lines: $(grep -iE 'minimum|upgrade bun|below' "$X/logs/b3-new.log" | cut -c1-200 | tr '\n' '|')"; echo "  bun installed into rd-sys: $(bunv "$REFLEX_DIR")"
REFLEX_USE_SYSTEM_BUN=1 run_init b3-prev "$PREVR" "$X/app-b3p" --template blank; echo "  warning lines (prev): $(grep -iE 'minimum|upgrade bun|below' "$X/logs/b3-prev.log" | cut -c1-200 | tr '\n' '|')"
unset REFLEX_DIR
echo "=== I1 fresh init in a dir named reflex"
for v in new prev; do r=$NEWR; [ $v = prev ] && r=$PREVR; d=$X/i1-$v/reflex; run_init i1-$v "$r" "$d" --template blank; echo "  msg: $(grep -iE 'error|reserved|cannot|invalid' "$X/logs/i1-$v.log" | cut -c1-200 | tr '\n' '|')"; done
echo "=== I2 init --name myapp in a dir named reflex, then re-init without --name"
for v in new prev; do r=$NEWR; [ $v = prev ] && r=$PREVR; d=$X/i2-$v/reflex; run_init i2a-$v "$r" "$d" --name myapp --template blank; echo "  app_name in rxconfig: $(grep app_name "$d/rxconfig.py" | tr -d ' ')"
  run_init i2b-$v "$r" "$d"; echo "  re-init msg: $(grep -iE 'error|reserved|cannot|invalid|Initializ' "$X/logs/i2b-$v.log" | cut -c1-200 | tr '\n' '|')"; done
echo "=== I3 re-init of an existing app in a normal dir (tree diff)"
for v in new prev; do r=$NEWR; [ $v = prev ] && r=$PREVR; d=$X/i3-$v/normalapp; run_init i3a-$v "$r" "$d" --template blank
  (cd "$d" && find . -path ./.web -prune -o -type f -print | sort | xargs sha256sum) > "$X/logs/i3-$v-before.txt"; run_init i3b-$v "$r" "$d"
  (cd "$d" && find . -path ./.web -prune -o -type f -print | sort | xargs sha256sum) > "$X/logs/i3-$v-after.txt"; echo "  tree diff after re-init: $(diff "$X/logs/i3-$v-before.txt" "$X/logs/i3-$v-after.txt" | grep -c '^[<>]') lines"; done
echo "=== I4 templates list, --version, export"
for v in new prev; do r=$NEWR; [ $v = prev ] && r=$PREVR; echo "-- $v: $($r --version 2>&1 | tail -1)"; d=$X/i4-$v/tpl; mkdir -p "$d"; (cd "$d" && $r init --template __bogus__ > "$X/logs/i4-$v-tpl.log" 2>&1; echo "  bogus template rc=$?"); grep -iE "template|blank|available" "$X/logs/i4-$v-tpl.log" | head -8 | cut -c1-200
  d=$X/i3-$v/normalapp; (cd "$d" && $r export > "$X/logs/i4-$v-export.log" 2>&1; echo "  export rc=$? zips: $(ls *.zip 2>/dev/null | tr '\n' ' ') errors: $(grep -ciE 'error|traceback' "$X/logs/i4-$v-export.log")"); done
echo "=== done $(date +%T)"
