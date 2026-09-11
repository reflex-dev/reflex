#!/bin/bash
# usage: conc.sh <reflex-bin> <appdir> <logdir> <tag> <workers> <trials> <cmd...>
BIN=$1; APP=$2; LOGD=$3; TAG=$4; W=$5; T=$6; shift 6
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p "$LOGD"
cd "$APP" || exit 2
fails=0; total=0
for t in $(seq 1 "$T"); do
  rm -rf assets/external
  pids=()
  for w in $(seq 1 "$W"); do
    ( timeout 900 "$BIN" "$@" > "$LOGD/${TAG}_t${t}_w${w}.log" 2>&1 ) &
    pids+=($!)
  done
  rcs=""
  for p in "${pids[@]}"; do wait "$p"; rc=$?; rcs="$rcs $rc"; total=$((total+1)); [ "$rc" -ne 0 ] && fails=$((fails+1)); done
  echo "trial $t rcs:$rcs"
  for f in shared.js shared.css; do
    L="assets/external/sharedapp/widget/$f"
    if [ -L "$L" ]; then tgt=$(readlink "$L"); case "$tgt" in *"/sharedapp/$f") ;; *) echo "  BADLINK $L -> $tgt";; esac
    else echo "  MISSING $L"; fi
  done
  ls assets/external/sharedapp/widget/ 2>/dev/null | tr '\n' ' '; echo
done
echo "FAILED $fails / $total"
