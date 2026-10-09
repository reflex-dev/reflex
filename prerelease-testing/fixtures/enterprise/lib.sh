# Sourced by every fixtures/enterprise script:  . "<path>/lib.sh"
# Resolves the fixture root from this file's location and sets the shared defaults (override any of them in the env).
FX=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
: "${SB:?export SB=<scratch root holding envs/ apps/ downloads/; see prerelease-testing/scripts/bootstrap_envs.sh>}"
: "${WORK:=$SB/apps/fx_enterprise}"   # runtime copies: app dirs (.web), logs/, shots/, out/, run/ — never inside the repo
: "${ENT_NEW:=new-ent}"               # venv under test: reflex + reflex-enterprise[mcp] + oidc-provider-mock
: "${DRV_VENV:=driver}"               # playwright + httpx + websockets (Playwright drivers)
: "${ENT_DRV:=ent-drv}"               # reflex + reflex-enterprise[mcp] + playwright (a4auth matrix + MCP clients); bin/build_ent_drv.sh
: "${IDP_VENV:=$ENT_NEW}"             # any venv with oidc-provider-mock (the mock IdP on :8638)
: "${CHROMIUM:=/opt/pw-browsers/chromium}"
export SB WORK ENT_NEW DRV_VENV ENT_DRV IDP_VENV CHROMIUM
export REFLEX_TELEMETRY_ENABLED=false
DRVPY=$SB/envs/$DRV_VENV/bin/python
# client-side commands only; never exported into a reflex server's environment
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"

# fx_sync <sub>: copy a sub-area's drivers/scripts (they write ../logs, ../shots, ../out next to themselves) into $WORK/<sub>
fx_sync() {
  local s=$1 d
  mkdir -p "$WORK/$s"/{logs,shots,screenshots,run,out,pids,runs}
  for d in drivers scripts a4auth bin; do
    [ -d "$FX/$s/$d" ] && (cd "$FX/$s" && tar --exclude=__pycache__ -cf - "$d") | (cd "$WORK/$s" && tar -xf -)
  done
  return 0
}

# fx_app <sub> <app> <name>: refresh $WORK/<sub>/<name> from $FX/<sub>/src/<app> (keeps an earlier copy's .web / db)
fx_app() {
  local d=$WORK/$1/$3
  mkdir -p "$d"
  (cd "$FX/$1/src/$2" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$d" && tar -xf -)
}

# venv_check <venv>: fail early (with a hint) when a required venv is missing
venv_check() {
  [ -x "$SB/envs/$1/bin/python" ] || { echo "missing venv $SB/envs/$1 (see fixtures/enterprise/README.md, Venvs)"; return 1; }
}

# acct_stub: the PyPI reflex-enterprise wheel refuses `reflex run --env prod` for a logged-out user; start the loopback
# account stub (account_stub.py, 127.0.0.1:8639) and export its env for the prod server. ENT_ACCOUNT_STUB=0 disables it
# (offline enterprise wheel, or a real `reflex login`). Harmless with the offline wheel (it never asks).
acct_stub() {
  [ "${ENT_ACCOUNT_STUB:-1}" = 1 ] || return 0
  if ! curl -s --noproxy '*' -o /dev/null http://127.0.0.1:8639/; then
    mkdir -p "$WORK"
    QA_FIXTURE_TOKEN=qa-fixture-token QA_ACCOUNT_AUDIT=$WORK/account-stub.jsonl \
      setsid "$DRVPY" -I "$FX/account_stub.py" > "$WORK/account-stub.log" 2>&1 < /dev/null &
    echo $! > "$WORK/account-stub.pid"
    for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null http://127.0.0.1:8639/ && break; sleep 0.25; done
  fi
  export REFLEX_ACCESS_TOKEN=qa-fixture-token REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:8639
}
acct_stub_stop() {
  [ -s "$WORK/account-stub.pid" ] && kill "$(cat "$WORK/account-stub.pid")" 2>/dev/null; rm -f "$WORK/account-stub.pid"
  for q in $(lsof -t -iTCP:8639 -sTCP:LISTEN 2>/dev/null); do kill "$q"; done
}
