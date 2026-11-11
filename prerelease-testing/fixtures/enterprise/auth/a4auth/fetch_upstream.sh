#!/usr/bin/env bash
# Materialize the upstream-derived parts of the 10-05 a4 auth matrix into $WORK/auth/a4auth (never into the repo):
#   reference/tests__integration__{auth_harness,test_auth_flow}.py  (imported by drive_auth.py / recheck_reload.py)
#   apps/auth/auth/auth.py                                          (AuthFlowApp lifted to module scope by lift_app.py)
# Source: a reflex-enterprise checkout (private repo github.com/reflex-dev/reflex-enterprise, at the tag/branch of the
# release under test). Usage: fetch_upstream.sh [<enterprise checkout>, default $ENT_REPO or /home/user/reflex-enterprise]
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; A=$WORK/auth/a4auth
R=${1:-${ENT_REPO:-/home/user/reflex-enterprise}}
[ -f "$R/tests/integration/test_auth_flow.py" ] || { echo "no reflex-enterprise checkout at $R (gh repo clone reflex-dev/reflex-enterprise)"; exit 1; }
mkdir -p "$A/reference" "$A/apps/auth/auth"
for f in auth_harness test_auth_flow; do cp "$R/tests/integration/$f.py" "$A/reference/tests__integration__$f.py"; done
: > "$A/apps/auth/auth/__init__.py"
(cd "$SB" && python3 -I "$A/lift_app.py" "$R/tests/integration/test_auth_flow.py" "$A/apps/auth/auth/auth.py")
echo "upstream rev: $(git -C "$R" log -1 --format='%h %cd' 2>/dev/null)"
