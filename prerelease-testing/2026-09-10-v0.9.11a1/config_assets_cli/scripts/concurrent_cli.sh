#!/bin/bash
# #7039: run N reflex CLI invocations concurrently in ONE app dir and report
# failures. Usage: concurrent_cli.sh <venv-bin-reflex> <appdir> <logdir> <tag> <workers> <trials> <cmd...>
REFLEXBIN=$1; APPDIR=$2; LOGDIR=$3; TAG=$4; WORKERS=$5; TRIALS=$6; shift 6
export REFLEX_TELEMETRY_ENABLED=false
cd "$APPDIR" || exit 2
fails=0
for t in $(seq 1 "$TRIALS"); do
  rm -rf assets/external
  pids=()
  for w in $(seq 1 "$WORKERS"); do
    ( timeout 600 "$REFLEXBIN" "$@" > "$LOGDIR/${TAG}_t${t}_w${w}.log" 2>&1 ) &
    pids+=($!)
  done
  rcs=""
  for i in "${!pids[@]}"; do
    wait "${pids[$i]}"; rc=$?; rcs="$rcs $rc"
    [ "$rc" -ne 0 ] && fails=$((fails+1))
  done
  echo "trial $t: exit codes:$rcs"
  # verify the links are correct afterwards
  for f in shared.js shared.css; do
    L="assets/external/sharedapp/widget/$f"
    if [ -L "$L" ]; then
      tgt=$(readlink "$L")
      case "$tgt" in *"/sharedapp/$f") ;; *) echo "  BAD LINK $L -> $tgt"; fails=$((fails+1));; esac
    else
      echo "  MISSING/NOT-A-LINK $L"; fails=$((fails+1))
    fi
  done
done
echo "TOTAL FAILURES: $fails"
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
