#!/bin/sh
# Invoke from neutral scratch; never install the checkout.
set -eu
SB=${1:?scratch root required}
DEST=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTPUT=${2:-"$DEST/environment"}
mkdir -p "$SB/apps/pymatrix_a2" "$OUTPUT"
export UV_CACHE_DIR="$SB/uv-cache"
export UV_PYTHON_INSTALL_DIR="$SB/uv-python"
cd "$SB/apps/pymatrix_a2"
for minor in 11 13 14; do
  case "$minor" in
    11) version=3.11.16 ;;
    13) version=3.13.15 ;;
    14) version=3.14.7 ;;
  esac
  target="$SB/envs/pymatrix-a2-3$minor"
  test ! -e "$target" || { echo "Refusing existing environment: $target"; exit 1; }
  uv --no-config venv --python "$version" "$target" > "$OUTPUT/3$minor-install.log" 2>&1
  uv --no-config pip install --python "$target/bin/python" --prerelease=allow --constraint "$DEST/environment/constraints.txt" 'reflex[pydantic]==0.10.0a2' 'pydantic==2.13.5' >> "$OUTPUT/3$minor-install.log" 2>&1
  uv --no-config pip freeze --python "$target/bin/python" > "$OUTPUT/3$minor.txt"
  REFLEX_TEST_ENV="pymatrix-a2-3$minor" uv --no-config run --no-project --python "$target/bin/python" python "$DEST/probe.py" > "$OUTPUT/3$minor.json"
  echo "READY pymatrix-a2-3$minor"
done
target="$SB/envs/pymatrix-a2-310-refusal"
test ! -e "$target" || { echo "Refusing existing environment: $target"; exit 1; }
uv --no-config venv --python 3.10.21 "$target" > "$OUTPUT/310-install.log" 2>&1
set +e
uv --no-config pip install --python "$target/bin/python" --prerelease=allow 'reflex==0.10.0a2' >> "$OUTPUT/310-install.log" 2>&1
code=$?
set -e
echo "$code" > "$OUTPUT/310-install.exit"
uv --no-config run --no-project --python "$target/bin/python" python -c 'import sys,importlib.util,json; spec=importlib.util.find_spec("reflex"); print(json.dumps({"python":sys.version,"reflex_spec":str(spec)})); assert spec is None' > "$OUTPUT/310-origin.json"
test "$code" -ne 0
