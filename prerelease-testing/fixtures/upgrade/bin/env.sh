# Sourced by every script of the `upgrade` fixture area. Sets the shared variables and helpers.
#   SB      scratch root (venvs in $SB/envs, downloads in $SB/downloads)
#   W       staged work copy of this area (bin/stage.sh copies the fixtures there; apps get .web/ etc. there)
#   NEW     venv name (under $SB/envs) of the version under test        (default: rel)
#   PREV    venv name of the previous release                           (default: rel)
#   NEW_VERSION / PREV_VERSION   version strings; default = reflex's version inside $NEW / $PREV
#   BASE_VERSION  version a "previous stable user" starts from in the in-place upgrades (default: $PREV_VERSION)
#   VENV_PREFIX   prefix of the per-fixture scratch venvs this area builds  (default: upgrade -> $SB/envs/upgrade-*)
#   DRIVER  venv name with playwright/httpx/websockets                  (default: driver)
: "${SB:?export SB=<scratch root holding envs/ apps/ downloads/; see prerelease-testing/scripts/bootstrap_envs.sh>}"
: "${W:=$SB/apps/upgrade}"
: "${NEW:=new}"
: "${PREV:=prev}"
: "${DRIVER:=driver}"
: "${VENV_PREFIX:=upgrade}"
export SB W NEW PREV DRIVER VENV_PREFIX
export REFLEX_TELEMETRY_ENABLED=false
UPG_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DPY=$SB/envs/$DRIVER/bin/python
# client-side commands only; never export NO_PROXY into a reflex server's environment
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout ${DRV_TIMEOUT:-900} $DPY"

ver_of() { # ver_of <venv-name> [dist] -> installed version of dist (default reflex)
  "$SB/envs/$1/bin/python" -I -c "import importlib.metadata as m,sys; print(m.version(sys.argv[1]))" "${2:-reflex}" 2>/dev/null
}
: "${NEW_VERSION:=$(ver_of "$NEW")}"
: "${PREV_VERSION:=$(ver_of "$PREV")}"
: "${BASE_VERSION:=$PREV_VERSION}"
export NEW_VERSION PREV_VERSION BASE_VERSION

uvq() { (cd "$SB" && uv --no-config "$@" 2>&1 | grep -v UV_NATIVE); }  # uv from a neutral cwd, never from a checkout
http_code() { curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "$1"; }
port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }
pre_flag() { case "$1" in *a*|*b*|*rc*|*dev*) echo --prerelease=allow;; esac; }  # uv needs it for an alpha pin
