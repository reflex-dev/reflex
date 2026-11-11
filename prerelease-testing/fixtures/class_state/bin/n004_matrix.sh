#!/bin/bash
# N-004 state-store interchange between versions, Python level. Usage: bin/n004_matrix.sh <outdir> <venv>...   (e.g. "$NEW" "$PREV" [$CTRL])
# (1) derive_h_schema.py: save SchemaState with each venv (default 0), load every save with every venv at default 0 and 5.
# (2) StateManagerDisk: writer saves, reader steps (load+mutate+save), writer loads again (shared REFLEX_STATES_WORKDIR).
# (3) schema hashes of several state shapes (probes/schema_hashes.py, probes/schema_hashes_sd.py).
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
OUT=$1; shift; mkdir -p "$OUT"
R=$W/run/n004; rm -rf "$R"; mkdir -p "$R/schema/out" "$R/disk"
cp "$CS"/probes/schema/*.py "$R/schema/"; cp "$CS"/probes/disk/*.py "$R/disk/"
D=$R/schema/out
( cd "$R/schema"
for s in "$@"; do
  echo "+ SCHEMA_DEFAULT=0 $s save"; SCHEMA_DEFAULT=0 "$SB/envs/$s/bin/python" derive_h_schema.py "$s" save "$D/saved-$s.bin"
  for l in "$@"; do for d in 0 5; do
    printf "saved=%-26s loader=%-26s d$d -> " "$s" "$l"; SCHEMA_DEFAULT=$d "$SB/envs/$l/bin/python" derive_h_schema.py "$l" load "$D/saved-$s.bin"
  done; done
done
echo "+ pickle contents"
for s in "$@"; do "$SB/envs/$DRIVER/bin/python" -I "$CS/probes/pickle_keys.py" "$D/saved-$s.bin"; done ) > "$OUT/schema_matrix.txt" 2>&1
( cd "$R/disk"
for w in "$@"; do for r in "$@"; do
  DD=$R/disk/st-$w-$r; rm -rf "$DD"; mkdir -p "$DD"; T=$(printf 'tok-%s-%s' "${w##*-}" "${r##*-}" | tr '_' 'x')  # client token must not contain "_"
  echo "== writer=$w reader=$r"
  REFLEX_STATES_WORKDIR=$DD "$SB/envs/$w/bin/python" -I disk_probe.py "$w" save "$T" 2>&1 | tail -n 1
  REFLEX_STATES_WORKDIR=$DD "$SB/envs/$r/bin/python" -I disk_probe.py "$r" step "$T" 2>&1 | tail -n 1
  REFLEX_STATES_WORKDIR=$DD "$SB/envs/$w/bin/python" -I disk_probe.py "$w" load "$T" 2>&1 | tail -n 1
done; done ) > "$OUT/disk_matrix.txt" 2>&1
( cd "$R"; for v in "$@"; do
  EXPECT_VENV=$v "$SB/envs/$v/bin/python" -I "$CS/probes/schema_hashes.py"
  EXPECT_VENV=$v "$SB/envs/$v/bin/python" -I "$CS/probes/schema_hashes_sd.py"
done ) > "$OUT/schema_hashes.txt" 2>&1
echo "wrote $OUT/{schema_matrix,disk_matrix,schema_hashes}.txt"
