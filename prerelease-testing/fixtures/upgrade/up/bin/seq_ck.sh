#!/usr/bin/env bash
# clock (rx.Cookie zone, bg tick, on_load reset): BASE_VERSION baseline -> ONE browser context kept open across stop ->
# in-place upgrade -> restart (clock_session.py, + a new tab right after the upgrade) -> up -> cold. Ports FP/BP (3494/8494).
set -u; . "$(dirname "$0")/common.sh"
A=$U/apps/clock; V=$(venv_of ck); FP=${FP:-3494}; BP=${BP:-8494}; S=$U/shots/ck; C=$U/ctl/ck
rm -rf "$A/.web" "$A/reflex.lock" "$A/.states" "$C"; mkdir -p "$S" "$C"
echo "### ck base $BASE_VERSION $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/ck-base.server.log" || exit 1
$DRV "$U/scripts/drive_clock.py" http://localhost:$FP/ "$S" ck-base | summ
pkgsnap "$A" ck-base
$DRV "$U/scripts/clock_session.py" http://localhost:$FP/ "$S" ck-session-up "$C" > "$U/logs/ck-session.driver.log" 2>&1 & SESS=$!
for i in $(seq 1 120); do [ -f "$C/ready" ] && break; sleep 1; done; echo "session ready: $([ -f "$C/ready" ] && echo yes || echo NO)"
"$U/bin/stop_app.sh" "$A" $FP $BP; touch "$C/down"
echo "### ck upgrade -> $NEW_VERSION $(date +%T)"; upgrade ck ck "reflex==$NEW_VERSION" ${UP_EXTRA:-}
echo "### ck up $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/ck-up.server.log" || exit 1
touch "$C/up"; for i in $(seq 1 240); do [ -f "$C/done" ] && break; sleep 1; done; wait $SESS; summ < "$U/logs/ck-session.driver.log"
pkgsnap "$A" ck-up; pkgdiff ck-base ck-up
$DRV "$U/scripts/drive_clock.py" http://localhost:$FP/ "$S" ck-up | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
echo "### ck cold $(date +%T)"; rm -rf "$A/.web"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/ck-cold.server.log" || exit 1
pkgsnap "$A" ck-cold; pkgdiff ck-up ck-cold
$DRV "$U/scripts/drive_clock.py" http://localhost:$FP/ "$S" ck-cold | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
for t in base up cold; do echo "--- ck-$t server-log warnings:"; logscan "$U/logs/ck-$t.server.log"; done
echo "### ck done $(date +%T)"
