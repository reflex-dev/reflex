#!/usr/bin/env bash
# Follow-up of sdist_matrix.sh: (1) list the .pyi files INSIDE the published sdist archives (core/dataeditor/radix/reflex
# at 0.10.1a1), (2) control: pip --no-binary install of core/dataeditor/radix at 0.10.0 and compare with the 0.10.0 wheel
# install (pure-prev venv), (3) a verbose pip build of core 0.10.1a1 to capture the stub-generation hook output.
set -u
: "${SB:?}"
OUT=$SB/apps/upgrade_packaging/sdist; mkdir -p "$OUT/archives" "$OUT/lists" "$OUT/logs"; cd "$SB"
DPY=$SB/envs/driver/bin/python
sdist_url() { curl -s "https://pypi.org/pypi/$1/$2/json" | "$DPY" -I -c "import json,sys; d=json.load(sys.stdin); print([u['url'] for u in d['urls'] if u['packagetype']=='sdist'][0])"; }
echo "=== (1) .pyi files inside the published sdists"
for spec in reflex-components-core==0.10.1a1 reflex-components-dataeditor==0.10.1a1 reflex-components-radix==0.10.1a1 reflex==0.10.1a1 reflex-components-core==0.10.0 reflex-components-dataeditor==0.10.0 reflex-components-radix==0.10.0; do
  pkg=${spec%%==*}; ver=${spec#*==}; u=$(sdist_url "$pkg" "$ver"); f=$OUT/archives/$(basename "$u")
  [ -f "$f" ] || curl -sL -o "$f" "$u"
  tar tzf "$f" | sed 's#^[^/]*/##' | sort > "$OUT/lists/$pkg-$ver.sdist-archive.txt"
  echo "$spec: $(wc -l < "$OUT/lists/$pkg-$ver.sdist-archive.txt") entries, $(grep -c '\.pyi$' "$OUT/lists/$pkg-$ver.sdist-archive.txt") .pyi, build-system: $(tar xzf "$f" -O --wildcards '*/pyproject.toml' | "$DPY" -I -c "import sys,tomllib; d=tomllib.loads(sys.stdin.read()); print(d['build-system']); print('  hooks:', {k:v for k,v in d.get('tool',{}).get('hatch',{}).get('build',{}).items() if 'hook' in k})")"
done
echo "=== (2) control: 0.10.0 sdist installs with pip"
files_of() { "$1/bin/python" -I - "$2" <<'EOF'
import importlib.metadata as m, sys
d = m.distribution(sys.argv[1])
for f in sorted(str(p) for p in (d.files or [])):
    if "__pycache__" in f or f.endswith(".pyc") or ".dist-info/" in f: continue
    print(f)
EOF
}
for spec in reflex-components-core==0.10.0 reflex-components-dataeditor==0.10.0 reflex-components-radix==0.10.0; do
  pkg=${spec%%==*}; V=$SB/envs/upgrade_packaging-sd-ctrl-$pkg; rm -rf "$V"
  uv --no-config venv -q --seed --python 3.12 "$V" 2>/dev/null
  "$V/bin/python" -m pip install --disable-pip-version-check --no-binary "$pkg" "$spec" > "$OUT/logs/sdist-ctrl-pip-$pkg.log" 2>&1; rc=$?
  files_of "$V" "$pkg" > "$OUT/lists/ctrl-$pkg.sdist.txt"; files_of "$SB/envs/upgrade_packaging-pure-prev" "$pkg" > "$OUT/lists/ctrl-$pkg.wheel.txt"
  echo "pip $spec rc=$rc pyi(sdist-built)=$(grep -c '\.pyi$' "$OUT/lists/ctrl-$pkg.sdist.txt") pyi(wheel)=$(grep -c '\.pyi$' "$OUT/lists/ctrl-$pkg.wheel.txt") diff=$(diff "$OUT/lists/ctrl-$pkg.wheel.txt" "$OUT/lists/ctrl-$pkg.sdist.txt" | grep -c '^[<>]')"
  diff "$OUT/lists/ctrl-$pkg.wheel.txt" "$OUT/lists/ctrl-$pkg.sdist.txt" | head -6
  rm -rf "$V"
done
echo "=== (3) verbose pip build of reflex-components-core 0.10.1a1 (hook output)"
V=$SB/envs/upgrade_packaging-sd-verbose; rm -rf "$V"; uv --no-config venv -q --seed --python 3.12 "$V" 2>/dev/null
"$V/bin/python" -m pip install --disable-pip-version-check -v --no-binary reflex-components-core reflex-components-core==0.10.1a1 > "$OUT/logs/sdist-pip-verbose-core.log" 2>&1; echo "rc=$?"
grep -n -iE "pyi|stub|hatch_reflex|hook|warning|error|skip" "$OUT/logs/sdist-pip-verbose-core.log" | grep -v "pip._internal\|Ignoring\|Link requires" | head -40
rm -rf "$V"
echo "=== done $(date +%T)"
