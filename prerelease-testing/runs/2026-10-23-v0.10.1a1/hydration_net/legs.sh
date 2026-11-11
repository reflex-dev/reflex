#!/bin/bash
# Usage: legs.sh <leg> [<leg>...]   (one app server at a time; every leg stops what it starts)
# Legs (ports 3142/8142 dev, proxy 8143; prod 3144, proxy 3145; h4mix 3146/8146):
#   dev_h0     new dev, trusted_proxy_hops=0 (default) + xff_proxy: XFF matrix (direct + proxied), /ip browser, /whoami,
#              then all hnet_drive scenarios (big, shared, cv, typed, ovr, cs)
#   dev_h1     new dev, HNET_HOPS=1: matrix + /ip browser + /whoami
#   dev_h2     new dev, HNET_HOPS=2: matrix + /ip browser
#   dev_env    new dev, REFLEX_TRUSTED_PROXY_HOPS=1 (env path): matrix
#   dev_bad    new dev, invalid values (-1, abc, true): startup must fail with ConfigError
#   dev_close  new dev behind close_proxy.py (100 kB frame limit): bigproxy scenario (#7605 backoff)
#   prod_h1    new prod single port 3144 + xff_proxy 3145, HNET_HOPS=1: matrix + /ip browser
#   prod_plain new prod 3144 direct: all hnet_drive scenarios
#   prev_dev   prev (0.10.0) dev + xff_proxy: matrix + /ip + all scenarios (baseline)
#   prev_close prev behind close_proxy: bigproxy (baseline)
#   h4_c21     run_h4.sh C21,C23 on new and prev (HYD-12 / C21 context)
#   storm_R    A3-11 Part R (deterministic) on the 0.10.0a3 control and on new
SB=${SB:?}; export WORK=${WORK:-$SB/apps/hydration_net}
. "$WORK/src/scripts/env.sh"
R=$WORK/run_hnet.sh; M=$WORK/xff_matrix.sh; P=$WORK/probes; O=$W/results/hnet; mkdir -p "$O"
DRIVE="$DRV $P/hnet_drive.py"
whoami_() { echo "## /whoami direct:"; $NP curl -s --noproxy '*' "http://localhost:$1/whoami"; echo; echo "## /whoami via proxy $2 (spoofed XFF 6.6.6.6):"; $NP curl -s --noproxy '*' -H 'X-Forwarded-For: 6.6.6.6' "http://localhost:$2/whoami"; echo; }
matrix_ip() {  # label FP BP PP venv
  "$M" "$1" "$3" "$4" | tee "$O/$1.matrix.txt"
  mkdir -p "$O/$1"; $NP timeout 300 $DRIVE --base "http://localhost:$2" --out "$O/$1" --only ip 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/$1.ip.txt"
}
for LEG in "$@"; do
  echo; echo "######## $LEG ($(date +%T))"
  case $LEG in
    dev_h0)
      "$R" new dev dev 3142 8142 --proxy 8143:append --probe-only -- HNET_HOPS=0 || continue
      matrix_ip dev-h0 3142 8142 8143; whoami_ 8142 8143 | tee "$O/dev-h0.whoami.txt"
      mkdir -p "$O/dev-h0-scen"; $NP timeout 900 $DRIVE --base http://localhost:3142 --out "$O/dev-h0-scen" --only big,shared,cv,typed,ovr,cs 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/dev-h0.scen.txt"
      "$R" stop dev; cp "$(ls -t "$W/logs/hnet-dev"-*.log | head -1)" "$O/dev-h0.server.log";;
    dev_h0m)
      "$R" new dev dev 3142 8142 --proxy 8143:append --probe-only -- HNET_HOPS=0 || continue
      "$M" dev-h0 8142 8143 | tee "$O/dev-h0.matrix.txt"
      "$R" stop dev;;
    dev_h1)
      "$R" new dev dev 3142 8142 --proxy 8143:append --probe-only -- HNET_HOPS=1 || continue
      matrix_ip dev-h1 3142 8142 8143; whoami_ 8142 8143 | tee "$O/dev-h1.whoami.txt"
      "$R" stop dev; cp "$(ls -t "$W/logs/hnet-dev"-*.log | head -1)" "$O/dev-h1.server.log";;
    dev_h2)
      "$R" new dev dev 3142 8142 --proxy 8143:append --probe-only -- HNET_HOPS=2 || continue
      matrix_ip dev-h2 3142 8142 8143
      "$R" stop dev;;
    dev_line)
      "$R" new dev dev 3142 8142 --proxy 8143:line --probe-only -- HNET_HOPS=1 || continue
      "$M" dev-line 8142 8143 | tee "$O/dev-line.matrix.txt"
      "$R" stop dev;;
    dev_env)
      "$R" new dev dev 3142 8142 --proxy 8143:append --probe-only -- REFLEX_TRUSTED_PROXY_HOPS=1 || continue
      "$M" dev-env 8142 8143 | tee "$O/dev-env.matrix.txt"
      "$R" stop dev;;
    dev_bad)
      for bad in "HNET_HOPS=-1" "REFLEX_TRUSTED_PROXY_HOPS=abc" "REFLEX_TRUSTED_PROXY_HOPS=-2" "REFLEX_TRUSTED_PROXY_HOPS=true"; do
        echo "## $bad"; "$F/scripts/srv.sh" start hnet-bad new dev "$WORK/hnet" 3142 8142 $bad > /dev/null; sleep 12
        LOG=$(ls -t "$W/logs/hnet-bad"-*.log | head -1); grep -n -i "trusted_proxy_hops\|ConfigError\|error" "$LOG" | head -5 | cut -c1-300
        "$F/scripts/srv.sh" stop hnet-bad > /dev/null
      done | tee "$O/dev-bad.txt";;
    dev_close)
      $DRV "$P/close_proxy.py" 8143 8142 100000 > "$W/logs/closeproxy-dev.log" 2>&1 & CP=$!
      "$R" new dev dev 3142 8142 --probe-only -- REFLEX_API_URL=http://localhost:8143 || { kill $CP; continue; }
      mkdir -p "$O/dev-close"; $NP timeout 600 $DRIVE --base http://localhost:3142 --out "$O/dev-close" --only bigproxy --big-proxy-base http://localhost:3142 --observe 15 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/dev-close.txt"
      "$R" stop dev; kill $CP; wait $CP 2>/dev/null; grep -c "closing" "$W/logs/closeproxy-dev.log" | sed 's/^/proxy closes: /' | tee -a "$O/dev-close.txt";;
    prod_h1)
      "$R" new prod prod 3144 3144 --proxy 3145:append --probe-only -- HNET_HOPS=1 || continue
      "$M" prod-h1 3144 3145 | tee "$O/prod-h1.matrix.txt"
      mkdir -p "$O/prod-h1"; $NP timeout 300 $DRIVE --base http://localhost:3145 --out "$O/prod-h1" --only ip 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/prod-h1.ip.txt"
      whoami_ 3144 3145 | tee "$O/prod-h1.whoami.txt"
      "$R" stop prod; cp "$(ls -t "$W/logs/hnet-prod"-*.log | head -1)" "$O/prod-h1.server.log";;
    prod_plain)
      "$R" new prod prod 3144 3144 --probe-only || continue
      mkdir -p "$O/prod-plain"; $NP timeout 900 $DRIVE --base http://localhost:3144 --out "$O/prod-plain" --only big,shared,cv,typed,ovr,cs,ip 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/prod-plain.txt"
      "$R" stop prod; cp "$(ls -t "$W/logs/hnet-prod"-*.log | head -1)" "$O/prod-plain.server.log";;
    prev_dev)
      "$R" prev dev prev 3142 8142 --proxy 8143:append --probe-only || continue
      VER=0.10.0 matrix_ip prev-dev 3142 8142 8143; whoami_ 8142 8143 | tee "$O/prev-dev.whoami.txt"
      mkdir -p "$O/prev-dev-scen"; $NP timeout 900 $DRIVE --base http://localhost:3142 --out "$O/prev-dev-scen" --only big,shared,cv,typed,ovr,cs 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/prev-dev.scen.txt"
      "$R" stop prev; cp "$(ls -t "$W/logs/hnet-prev"-*.log | head -1)" "$O/prev-dev.server.log";;
    prev_close)
      $DRV "$P/close_proxy.py" 8143 8142 100000 > "$W/logs/closeproxy-prev.log" 2>&1 & CP=$!
      "$R" prev dev prev 3142 8142 --probe-only -- REFLEX_API_URL=http://localhost:8143 || { kill $CP; continue; }
      mkdir -p "$O/prev-close"; $NP timeout 600 $DRIVE --base http://localhost:3142 --out "$O/prev-close" --only bigproxy --big-proxy-base http://localhost:3142 --observe 15 2>&1 | grep -E "^\[|^SUMMARY" | tee "$O/prev-close.txt"
      "$R" stop prev; kill $CP; wait $CP 2>/dev/null; grep -c "closing" "$W/logs/closeproxy-prev.log" | sed 's/^/proxy closes: /' | tee -a "$O/prev-close.txt";;
    h4_c21)
      "$F/scripts/run_h4.sh" new dev new-dev 3146 8146 - C21,C23 2>&1 | tail -8 | tee "$O/h4-new.txt"
      "$F/scripts/run_h4.sh" prev dev prev-dev 3146 8146 - C21,C23 2>&1 | tail -8 | tee "$O/h4-prev.txt";;
    storm_R)
      for v in hydration_net-0.10.0a3 new; do rm -f "$W/results/sync/storm_${v}_dev_R_6_"*.json; "$F/scripts/run_storm.sh" "$v" dev 2 3142 8142 R 6 > "$O/stormR-$v.txt" 2>&1; "$DRV" "$F/scripts/summ_s.py" "$W/results/sync/storm_${v}_dev_R_6_" | tee -a "$O/stormR-$v.txt"; done;;
    *) echo "unknown leg $LEG";;
  esac
done
