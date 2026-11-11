#!/usr/bin/env bash
# Build a wheel from a published sdist with pip (isolated build env unless NOISO=1), log verbosely, count .pyi.
# usage: pipwheel.sh <venv> <label> <sdist.tar.gz> [extra pip args...]
set -u
: "${SB:?}"; V=$1; label=$2; sdist=$3; shift 3
W=$SB/apps/verify_up/wheels/$label; rm -rf "$W"; mkdir -p "$W"; L=$SB/apps/verify_up/logs/pipwheel-$label.log
cd "$SB"
"$V/bin/python" -m pip wheel --disable-pip-version-check -v --no-deps -w "$W" "$@" "$sdist" > "$L" 2>&1; rc=$?
whl=$(ls "$W"/*.whl 2>/dev/null | head -1)
n=$([ -n "$whl" ] && "$SB/envs/driver/bin/python" -I "$SB/apps/verify_up/bin/wheel_pyi.py" "$whl" | head -1 | sed 's/.*: //')
base=$(grep -oE "reflex[-_]base-[0-9a-z.]+(-py3-none-any\.whl|\.tar\.gz)|Collecting reflex-base.*|reflex-base==[0-9a-z.]+" "$L" | sort -u | tr '\n' ' ')
echo "$label rc=$rc wheel=$(basename "${whl:-none}") pyi=[$n] build-env-base=[$base]"
