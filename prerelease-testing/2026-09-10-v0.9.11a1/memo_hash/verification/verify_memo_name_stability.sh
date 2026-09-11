#!/bin/bash
# Minimal repro: a dynamic `id=f"...{Var}..."` makes the auto-memo module name
# change on every compile, because Component.get_ref() fails to recognise the
# f-string form as dynamic and bakes hash(Var) into a generated JS identifier.
#
# Usage: verify_memo_name_stability.sh <app_dir> <path/to/bin/reflex> [n]
set -eu
APP="$1"; RFX="$2"; N="${3:-3}"
cd "$APP"
for i in $(seq 1 "$N"); do
  rm -rf .web/app_components .web/utils/components
  REFLEX_TELEMETRY_ENABLED=false "$RFX" compile >/dev/null 2>&1
  f=$(ls .web/app_components/*/*.jsx | head -1)
  printf 'compile %s: %-60s %s\n' "$i" \
    "$(grep -o 'export const [A-Za-z0-9_]*' "$f" | grep -vi errorboundary | head -1)" \
    "$(grep -o 'ref_[A-Za-z0-9_]*' "$f" | head -1)"
done
