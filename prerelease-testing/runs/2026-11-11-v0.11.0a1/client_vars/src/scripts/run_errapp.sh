#!/usr/bin/env bash
# `reflex compile` errapp once per misuse case; prints the exit code and the last lines a user sees.
# Usage: run_errapp.sh <venv> [case ...]
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$SB/apps/client_vars
V=$1; shift
CASES=${*:-none prop_pydantic prop_dataclass prop_foreach backend_child backend_fstring backend_id backend_typed_prop backend_image backend_toast backend_event_arg backend_eq page_title page_meta page_on_load page_decorator storage_factory storage_factory_cookie}
cd "$W/errapp" || exit 1
mkdir -p "$W/results/err"
for c in $CASES; do
  out=$W/results/err/${V}_$c.txt
  REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$V ERR_CASE=$c timeout 300 "$SB/envs/$V/bin/reflex" compile > "$out" 2>&1
  rc=$?
  echo "=== $V $c exit=$rc"
  grep -v '^\s*$' "$out" | grep -v -i -E 'sitemap|plugins. list|this plugin' | tail -4 | cut -c1-600
  grep -n -E 'errapp/errapp.py", line|errapp.py:[0-9]+' "$out" | tail -2 | cut -c1-200
done
