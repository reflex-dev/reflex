#!/bin/bash
# Usage: run_area.sh [quick|full]      (one app server at a time; everything it starts it stops)
#   NEW         venv under test (required), e.g. NEW=rc1 -> $SB/envs/rc1
#   PREV        previous release venv (optional; full: same storm/stamp/rtr series as a baseline)
#   CTRL_F002   positive control for F-002/F-003 (a venv with reflex 0.10.0a1, e.g. "alpha"; optional)
#   CTRL_STORM  positive control for A3-11/A3-12 (0.10.0a3, e.g. "a3"; optional)
#   CTRL_RTR    positive control for #7360 (0.10.0a4, e.g. "a4"; optional; it LEAKS by design)
#   TP_NEW      third-party auth venv for NEW (scripts/build_venvs.sh; optional; full only)
# quick (~10 min): probe, F-002 prod, cvstore dev seed 4, A3-11 storm dev x3, A3-12 stamp dev x2 + /same, #7360 rtr dev.
# full adds: F-002 dev + prod+Redis, cvstore prod, storm/stamp prod, rtr prod + prod+Redis, h4mix C-matrix, A4-03 race,
#   hydapp sweep (F-008), F-010 prenav, reconnect/Redis restart, csbox/mini, no-__init__ case, google-auth/local-auth,
#   100 ms RTT verifier matrix (needs xvfb-run).
. "$(dirname "$0")/env.sh"
: "${NEW:?set NEW to the venv under test}"
MODE=${1:-quick}; S=$F/scripts; O=$W/results/area; mkdir -p "$O"
has() { [ -n "${1:-}" ] && [ -x "$SB/envs/$1/bin/reflex" ]; }
step() { echo; echo "######## $* ($(date +%T))"; }
step probe; (cd "$W" && "$SB/envs/$NEW/bin/python" -I "$F/probes/cs_storage_default_probe.py" "$NEW") 2>&1 | tail -8
has "${CTRL_F002:-}" && { step "F-002 control $CTRL_F002 prod"; "$S/run_f002.sh" "$CTRL_F002" prod ctrl-prod 3140 3140 | tee "$O/f002_ctrl.txt"; }
step "F-002 $NEW prod"; "$S/run_f002.sh" "$NEW" prod new-prod 3140 3140 | tee "$O/f002_new_prod.txt"
has "${CTRL_F002:-}" && { step "F-003 control $CTRL_F002 dev s4 a b g"; "$S/run_cv.sh" "$CTRL_F002" dev ctrl-dev-s4 3142 8142 "a b g" PYTHONHASHSEED=4 | tee "$O/cv_ctrl.txt"; }
step "F-003 cvstore $NEW dev s4"; "$S/run_cv.sh" "$NEW" dev new-dev-s4 3142 8142 all PYTHONHASHSEED=4 | tee "$O/cv_new_dev_s4.txt"
summ() { "$DRV" "$S/summ_s.py" "$W/results/sync/storm_$1_S_6_"; }   # storm verdict: "storms k/n"
has "${CTRL_STORM:-}" && { step "A3-11 control $CTRL_STORM"; rm -f "$W/results/sync/storm_${CTRL_STORM}_dev_S_6_"*.json; "$S/run_storm.sh" "$CTRL_STORM" dev 3 3142 8142 S 6 > "$O/storm_ctrl.txt"; summ "${CTRL_STORM}_dev" | tee -a "$O/storm_ctrl.txt"; }
step "A3-11 storm $NEW dev"; rm -f "$W/results/sync/storm_${NEW}_dev_S_6_"*.json; "$S/run_storm.sh" "$NEW" dev 3 3142 8142 S 6 > "$O/storm_new_dev.txt"; summ "${NEW}_dev" | tee -a "$O/storm_new_dev.txt"
has "${CTRL_STORM:-}" && { step "A3-12 control $CTRL_STORM"; "$S/run_stamp2.sh" "$CTRL_STORM" dev 3142 8142 2 1 6 | tee "$O/stamp_ctrl.txt"; }
step "A3-12 stamp $NEW dev"; "$S/run_stamp2.sh" "$NEW" dev 3142 8142 2 1 6 | tee "$O/stamp_new_dev.txt"
has "${CTRL_RTR:-}" && { step "#7360 control $CTRL_RTR dev"; "$S/run_rtr.sh" "$CTRL_RTR" dev ctrl-dev 3142 8142 8143 | tee "$O/rtr_ctrl.txt"; }
step "#7360 rtr $NEW dev"; "$S/run_rtr.sh" "$NEW" dev new-dev 3142 8142 8143 | tee "$O/rtr_new_dev.txt"
has "${CTRL_RTR:-}" && "$DRV" "$F/drivers/cmp_rtr.py" "$W/results/rtr/ctrl-dev.json" "$W/results/rtr/new-dev.json" | tail -15
[ "$MODE" = full ] || exit 0
step "F-002 dev"; "$S/run_f002.sh" "$NEW" dev new-dev 3142 8142 | tee "$O/f002_new_dev.txt"
step "F-002 prod+Redis"; redis_up && "$S/run_f002.sh" "$NEW" prod new-prodredis 3144 3144 REFLEX_REDIS_URL=redis://localhost:$REDIS_PORT | tee "$O/f002_new_prodredis.txt"; redis_down
step "cvstore prod s4 + client-nav (N-015)"; NAV=1 "$S/run_cv.sh" "$NEW" prod new-prod-s4 3144 3144 all PYTHONHASHSEED=4 | tee "$O/cv_new_prod_s4.txt"
step "storm/stamp prod"; rm -f "$W/results/sync/storm_${NEW}_prod_S_6_"*.json; "$S/run_storm.sh" "$NEW" prod 3 3144 3144 S 6 > "$O/storm_new_prod.txt"; summ "${NEW}_prod" | tee -a "$O/storm_new_prod.txt"; "$S/run_stamp2.sh" "$NEW" prod 3144 3144 2 1 6 | tee "$O/stamp_new_prod.txt"
has "${PREV:-}" && { step "baseline $PREV storm/stamp/rtr dev"; rm -f "$W/results/sync/storm_${PREV}_dev_S_6_"*.json; "$S/run_storm.sh" "$PREV" dev 3 3142 8142 S 6 > /dev/null; summ "${PREV}_dev"; "$S/run_stamp2.sh" "$PREV" dev 3142 8142 2 1 6; "$S/run_rtr.sh" "$PREV" dev prev-dev 3142 8142 8143; "$DRV" "$F/drivers/cmp_rtr.py" "$W/results/rtr/prev-dev.json" "$W/results/rtr/new-dev.json" | tail -15; }
step "rtr prod + prod+Redis"; "$S/run_rtr.sh" "$NEW" prod new-prod 3144 3144 3145; "$S/run_rtr_redis.sh" "$NEW" new-prodredis
step "bootecho (#7493)"; "$S/run_be.sh" "$NEW" dev new-dev 3142 8142 | tail -30
step "h4mix C-matrix (#7505)"; "$S/run_h4.sh" "$NEW" dev new-dev 3146 8146 -
step "A4-03 race"; "$S/run_race.sh" "$NEW" new-dev 3660 8660 - 3
step "hydapp sweep"; "$S/run_hyd.sh" "$NEW" prod new-prod 3148 3148
step "F-010 prenav"; "$S/run_prenav.sh" "$NEW" new 3148 3149
step "reconnect / Redis restart"; "$S/run_reconnect.sh" "$NEW" 3150 3151 3
step "csbox / mini"; "$S/run_csbox_mini.sh" "$NEW"
step "no __init__.py"; "$S/run_noinit.sh" "$NEW"
has "${TP_NEW:-}" && { step "auth packages"; "$S/run_la.sh" "$TP_NEW" dev new-dev 3153 8153; "$S/run_gauth.sh" "$TP_NEW" dev new-dev-s4 3142 8142 4; }
command -v xvfb-run > /dev/null && { step "100 ms RTT verifier matrix"; "$S/vmatrix.sh" "$NEW" dev 3 3; }
step done
