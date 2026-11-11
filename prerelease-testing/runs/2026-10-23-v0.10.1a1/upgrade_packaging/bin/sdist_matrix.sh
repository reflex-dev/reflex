#!/usr/bin/env bash
# #7411: every changed train package installs from its sdist (--no-binary <pkg>) with uv and with pip, each in a fresh
# py3.12 venv ($SB/envs/upgrade_packaging-sd-<tool>-<pkg>), then the installed file list is compared with the wheel
# install in $SB/envs/new (same version). Output: logs/sdist-<tool>-<pkg>.log, lists in lists/, summary on stdout.
set -u
: "${SB:?}"
OUT=${OUT:-$SB/apps/upgrade_packaging/sdist}; mkdir -p "$OUT/logs" "$OUT/lists"; cd "$SB"
PKGS=${PKGS:-"reflex==0.10.1a1 reflex-base==0.10.1a1 reflex-components-code==0.10.1a1 reflex-components-core==0.10.1a1 reflex-components-dataeditor==0.10.1a1 reflex-components-moment==0.10.1a1 reflex-components-radix==0.10.1a1 reflex-components-lucide==1.1.1a1 reflex-hosting-cli==0.2.1a1 reflex-release==0.2.1a1 reflex-build-sdk==0.1.1a1"}
WHEEL_ENV=${WHEEL_ENV:-$SB/envs/new}
files_of() { # files_of <venv> <dist> -> sorted RECORD paths of the dist (without hashes), excluding __pycache__
  "$1/bin/python" -I - "$2" <<'EOF'
import importlib.metadata as m, sys
d = m.distribution(sys.argv[1])
for f in sorted(str(p) for p in (d.files or [])):
    if "__pycache__" in f or f.endswith(".pyc") or ".dist-info/" in f: continue
    print(f)
EOF
}
for spec in $PKGS; do
  pkg=${spec%%==*}
  for tool in uv pip; do
    V=$SB/envs/upgrade_packaging-sd-$tool-$pkg; rm -rf "$V"; L=$OUT/logs/sdist-$tool-$pkg.log
    if [ $tool = uv ]; then
      uv --no-config venv -q --python 3.12 "$V" 2>/dev/null
      uv --no-config pip install --python "$V/bin/python" --prerelease=allow --no-binary "$pkg" "$spec" > "$L" 2>&1; rc=$?
    else
      uv --no-config venv -q --seed --python 3.12 "$V" 2>/dev/null
      "$V/bin/python" -m pip install --disable-pip-version-check --no-binary "$pkg" "$spec" > "$L" 2>&1; rc=$?
    fi
    built=$(grep -oE "Built $pkg[^ ]*|Building wheel for $pkg[^)]*\)|Successfully built [^ ]*" "$L" | head -2 | tr '\n' ';')
    ver=$("$V/bin/python" -I -c "import importlib.metadata as m,sys; print(m.version(sys.argv[1]))" "$pkg" 2>&1 | tail -1)
    files_of "$V" "$pkg" > "$OUT/lists/$tool-$pkg.sdist.txt" 2>/dev/null
    files_of "$WHEEL_ENV" "$pkg" > "$OUT/lists/$pkg.wheel.txt" 2>/dev/null
    nd=$(diff "$OUT/lists/$pkg.wheel.txt" "$OUT/lists/$tool-$pkg.sdist.txt" | grep -c '^[<>]')
    pyi=$(grep -c '\.pyi$' "$OUT/lists/$tool-$pkg.sdist.txt")
    echo "$tool $spec rc=$rc installed=$ver built=[$built] files=$(wc -l < "$OUT/lists/$tool-$pkg.sdist.txt") pyi=$pyi diff-vs-wheel=$nd"
    [ "$nd" != 0 ] && diff "$OUT/lists/$pkg.wheel.txt" "$OUT/lists/$tool-$pkg.sdist.txt" | head -6
    [ $rc != 0 ] && { echo "  --- tail of $L"; tail -15 "$L" | sed 's/^/  /'; }
    rm -rf "$V"
  done
done
echo "=== sdist matrix done $(date +%T)"
