#!/bin/bash
# v5_admin.sh <venv-name> <appdir> <backend-port> : backend-only run of an adm app (see verify_dbm/admin_new/adm/adm.py),
# then GET /admin (no slash) and POST "New" for the MappedAsDataclass Tag and the SQLModel Label.
# Setup: cp -a <verify_dbm>/admin_app $SB/apps/verify_dbm/admin_new  (api_transformer recipe, no auth provider: test only)
#   0.10.1 rx.AdminDash variant: copy again to admin_prev_dash and replace the last App line with
#   `app = rx.App(admin_dash=rx.AdminDash(models=[Tag, Label]))`
# Ran: v5_admin.sh vdbm-new .../admin_new 8644 ; vdbm-prev .../admin_prev_xf 8643 ; vdbm-prev .../admin_prev_dash 8642
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; W=$2; P=$3; cd $W; export REFLEX_TELEMETRY_ENABLED=false
[ -f alembic.ini ] || { $V/bin/reflex db init > init.log 2>&1; echo "init rc=$?"; }
curl -s --noproxy '*' localhost:$P >/dev/null && { echo "port $P busy"; exit 1; }
setsid $V/bin/reflex run --backend-only --backend-port $P > run.log 2>&1 &
PG=$!
for i in $(seq 1 40); do c=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" localhost:$P/ping); [ "$c" = 200 ] && break; python3 -c "import time;time.sleep(1)"; done; echo "ping $c"
B=http://localhost:$P
for p in /admin /admin/; do echo "GET $p -> $(curl -s --noproxy '*' -o /dev/null -w '%{http_code} %{redirect_url}' $B$p)"; done
for m in tag label; do rm -f cj; tok=$(curl -s --noproxy '*' -c cj -b cj $B/admin/$m/create | grep -o 'name="csrftoken" value="[^"]*"' | sed 's/.*value="//;s/"$//')
  echo "POST /admin/$m/create -> $(curl -s --noproxy '*' -c cj -b cj -o post_$m.html -w '%{http_code} %{redirect_url}' ${tok:+-F csrftoken=$tok} -F name=x$m $B/admin/$m/create)"; done
grep -E "TypeError" run.log | head -n 3
PGID=$(ps -o pgid= -p $(pgrep -P $PG | head -1) 2>/dev/null | tr -d ' '); PGID=${PGID:-$PG}
kill -- -$PGID 2>/dev/null || kill -- -$((PG+1)) 2>/dev/null; python3 -c "import time;time.sleep(2)"; kill -9 -- -$PGID 2>/dev/null; true
