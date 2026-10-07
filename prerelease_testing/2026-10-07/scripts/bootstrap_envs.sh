#!/usr/bin/env bash
# Build the isolated PyPI-only environments every brief refers to as $SB/envs/<name>.
# usage: scripts/bootstrap_envs.sh <scratch-dir> [--enterprise]   (then: export SB=<scratch-dir>)
# Never run uv with a reflex checkout as cwd (its pyproject's exclude-newer window hides fresh packages).
set -euo pipefail
SB="${1:?usage: bootstrap_envs.sh <scratch-dir> [--enterprise]}"; ENT="${2:-}"
mkdir -p "$SB/envs" "$SB/apps" "$SB/logs" "$SB/downloads"; cd "$SB"
PY="${PYTHON_VERSION:-3.12}"
mk() { # name, pip args...
  local name="$1"; shift
  [ -x "$SB/envs/$name/bin/python" ] || uv --no-config venv --python "$PY" "$SB/envs/$name"
  uv --no-config pip install --python "$SB/envs/$name/bin/python" "$@"
}
mk alpha2 --prerelease=allow 'reflex[db]==0.10.0a2' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14'
mk alpha  --prerelease=allow 'reflex[db]==0.10.0a1' 'reflex-hosting-cli==0.1.73a1' 'pydantic<2.14'
mk stable 'reflex[db]==0.9.12'
mk driver playwright httpx websockets pip
"$SB/envs/driver/bin/python" -m playwright install chromium >/dev/null 2>&1 || echo "playwright chromium install failed; set CHROMIUM path manually (e.g. /opt/pw-browsers/chromium)"
if [ "$ENT" = "--enterprise" ]; then
  W="$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl"
  if [ -f "$W" ]; then
    mk alpha2-ent --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14' "$W[mcp]" oidc-provider-mock
  else
    echo "offline enterprise wheel not found at $W — falling back to PyPI reflex-enterprise==0.9.7a4 (needs CI=true at runtime)"
    mk alpha2-ent --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14' 'reflex-enterprise[mcp]==0.9.7a4' oidc-provider-mock
  fi
fi
for e in alpha2 alpha stable; do echo "== $e: $("$SB/envs/$e/bin/python" -c 'import reflex, reflex_base; print(reflex.__file__.split("/site-packages/")[0].rsplit("/",3)[0])' 2>/dev/null) $("$SB/envs/$e/bin/reflex" --version 2>/dev/null)"; done
echo "export SB=$SB"
