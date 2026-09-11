#!/bin/bash
# Are generated memo module names stable across identical compiles?
# Usage: name_stability.sh <app_dir> <venv_bin_reflex> <outdir>
set -eu
APP="$1"; RFX="$2"; OUT="$3"
mkdir -p "$OUT"
names() { grep -ho "export const [A-Za-z0-9_]*" "$APP"/.web/app_components/*/*.jsx "$APP"/.web/utils/components/*.jsx 2>/dev/null | sort; }
cd "$APP"
for i in 1 2 3; do
  rm -rf .web/app_components .web/utils/components
  REFLEX_TELEMETRY_ENABLED=false "$RFX" compile >/dev/null 2>&1
  names > "$OUT/compile_$i.txt"
  echo "compile $i: $(wc -l < "$OUT/compile_$i.txt") memo names"
done
# same again but with the .web tree fully removed (cold)
rm -rf .web/app_components .web/utils/components
REFLEX_TELEMETRY_ENABLED=false "$RFX" export --no-zip --frontend-only >/dev/null 2>&1 || true
names > "$OUT/export_1.txt"
REFLEX_TELEMETRY_ENABLED=false "$RFX" export --no-zip --frontend-only >/dev/null 2>&1 || true
names > "$OUT/export_2.txt"
echo "export 1: $(wc -l < "$OUT/export_1.txt")  export 2: $(wc -l < "$OUT/export_2.txt")"
echo "--- diffs ---"
diff "$OUT/compile_1.txt" "$OUT/compile_2.txt" && echo "compile_1 == compile_2"
diff "$OUT/compile_2.txt" "$OUT/compile_3.txt" && echo "compile_2 == compile_3"
diff "$OUT/compile_3.txt" "$OUT/export_1.txt" && echo "compile_3 == export_1"
diff "$OUT/export_1.txt" "$OUT/export_2.txt" && echo "export_1 == export_2"
