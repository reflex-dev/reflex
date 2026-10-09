#!/usr/bin/env bash
# N-001 / F-005 / F-006 install paths for NEW_VERSION: fresh venvs, NOTHING added by hand.
#   pip: no --pre (an exact ==X pin is explicit); uv: $(pre_flag) i.e. --prerelease=allow only for a pre-release pin
#   (uv refuses an alpha pin without it: pre-existing uv semantics; force with UVFLAG=...).
# Venvs: $SB/envs/$VENV_PREFIX-n001-<key>. SPECS = "key:tool:python:kind ..." (kind db = 'reflex[db]==X', plain = 'reflex==X' = F-006)
# Output: logs/install-<key>.log, logs/freeze-<key>.txt; summary on stdout.
set -u; . "$(dirname "$0")/../../bin/env.sh"; I=$(cd "$(dirname "$0")/.." && pwd); L=$I/logs; mkdir -p "$L"
X=${INST_VERSION:-$NEW_VERSION}
pkgs() { "$1/bin/python" -I -c "
import importlib.metadata as m
def g(p):
    try: return m.version(p)
    except Exception: return 'NOT-INSTALLED'
print(' '.join(p+'='+g(p) for p in ['reflex','reflex-base','sqlalchemy','sqlmodel','greenlet','alembic','pydantic','reflex-components-core','reflex-components-radix','reflex-hosting-cli','reflex-build-sdk']))"; }
for spec in ${SPECS:-uv311:uv:3.11:db uv314:uv:3.14:db pip311:pip:3.11:db pip314:pip:3.14:db f006pip312:pip:3.12:plain}; do
  IFS=: read -r k tool py kind <<< "$spec"; V=$SB/envs/$VENV_PREFIX-n001-$k; rm -rf "$V"
  req="reflex[db]==$X"; [ "$kind" = plain ] && req="reflex==$X"
  if [ "$tool" = uv ]; then
    uvq venv -q --python "$py" "$V"
    (cd "$SB" && uv --no-config pip install --python "$V/bin/python" ${UVFLAG:-$(pre_flag "$X")} "$req" > "$L/install-$k.log" 2>&1); rc=$?
  else
    uvq venv -q --seed --python "$py" "$V"
    (cd "$SB" && "$V/bin/python" -m pip install --disable-pip-version-check "$req" > "$L/install-$k.log" 2>&1); rc=$?
  fi
  (cd "$SB" && "$V/bin/python" -m pip freeze 2>/dev/null) > "$L/freeze-$k.txt" || uvq pip freeze --python "$V/bin/python" > "$L/freeze-$k.txt"
  echo "py$py/$tool '$req' rc=$rc: $(pkgs "$V")"
  echo "  pre-releases in graph: $(grep -E '(a|b|rc)[0-9]+$|\.dev' "$L/freeze-$k.txt" | tr '\n' ' ')"
  (cd "$SB" && "$V/bin/python" -I -c "import reflex.model; print('  import reflex.model OK')" 2>&1 | tail -1)
  if [ "$tool" = pip ]; then (cd "$SB" && "$V/bin/python" -m pip check 2>&1 | tail -1 | sed 's/^/  pip check: /'); else uvq pip check --python "$V/bin/python" | tail -1 | sed 's/^/  uv pip check: /'; fi
done
