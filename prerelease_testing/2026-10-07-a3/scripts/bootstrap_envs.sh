#!/usr/bin/env bash
# Build the isolated PyPI-only environments every a3 brief refers to as $SB/envs/<name>.
# usage: scripts/bootstrap_envs.sh <scratch-dir> [--enterprise]   (then: export SB=<scratch-dir>)
# Never run uv with a reflex checkout as cwd (its pyproject's exclude-newer window hides fresh packages).
# Existing venvs are reused; delete one to rebuild it.
set -euo pipefail
SB="${1:?usage: bootstrap_envs.sh <scratch-dir> [--enterprise]}"; ENT="${2:-}"
mkdir -p "$SB/envs" "$SB/apps" "$SB/logs" "$SB/downloads"; cd "$SB"
PY="${PYTHON_VERSION:-3.12}"
mk() { # name, pip args...
  local name="$1"; shift
  [ -x "$SB/envs/$name/bin/python" ] && return 0
  uv --no-config venv -q --python "$PY" "$SB/envs/$name"
  uv --no-config pip install -q --python "$SB/envs/$name/bin/python" "$@"
}
# Version under test. greenlet must arrive through the db extra now (#7466): do NOT add it by hand here.
mk a3     --prerelease=allow 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14'
# Previous alpha (before/after for #7493/#7495). greenlet added by hand (N-001 was unfixed in a2).
mk alpha2 --prerelease=allow 'reflex[db]==0.10.0a2' 'reflex-base==0.10.0a2' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' greenlet
# Previous stable baseline. greenlet by hand (fresh 0.9.12 installs resolve SQLAlchemy 2.1 too).
mk stable 'reflex[db]==0.9.12' greenlet
mk driver playwright httpx websockets pip
[ -x /opt/pw-browsers/chromium ] || "$SB/envs/driver/bin/python" -m playwright install chromium >/dev/null 2>&1 \
  || echo "playwright chromium install failed; set the Chromium path manually"
if [ "$ENT" = "--enterprise" ]; then
  W5="$SB/downloads/enterprise_wheel_a5/reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl"
  W4="$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl"
  [ -f "$W5" ] || { echo "offline enterprise 0.9.7a5 wheel missing at $W5 (ask the user for it)"; exit 3; }
  mk a3-ent  --prerelease=allow 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' "$W5[mcp]" oidc-provider-mock
  mk s912-ent-a5 'reflex[db]==0.9.12' greenlet "$W5[mcp]" oidc-provider-mock
  if [ -f "$W4" ]; then
    # reflex a3 with the OLD enterprise wheel: shows what users who upgrade reflex but not enterprise get (N-025).
    mk a3-ent-a4 --prerelease=allow 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' "$W4[mcp]" oidc-provider-mock
  fi
fi
for e in a3 alpha2 stable a3-ent s912-ent-a5 a3-ent-a4; do
  [ -x "$SB/envs/$e/bin/python" ] || continue
  echo "== $e: $(cd "$SB" && "$SB/envs/$e/bin/python" -I -c 'import importlib.metadata as m
out = []
for p in ("reflex", "reflex-base", "reflex-enterprise", "sqlalchemy", "greenlet"):
    try: out.append(f"{p}={m.version(p)}")
    except m.PackageNotFoundError: out.append(f"{p}=-")
print(" ".join(out))')"
done
echo "export SB=$SB"
