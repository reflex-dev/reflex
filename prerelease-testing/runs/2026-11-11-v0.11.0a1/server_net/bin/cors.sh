#!/usr/bin/env bash
# Split-origin CORS matrix: static export on FP (python http.server) + `reflex run --env prod --backend-only` on BP.
#   cors.sh <venv> <label> [ENV=VAL ...]     (static site: $W/static/<venv>/site exported with REFLEX_API_URL=http://localhost:BP)
# MODE=dev runs the backend without --env prod.  BROWSER=0 skips the Chromium run.
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1 label=$2; shift 2
FP=${FP:-3346} BP=${BP:-8346}
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
DPY=$SB/envs/driver/bin/python
for p in $FP $BP; do curl --noproxy '*' -s -m 1 localhost:$p >/dev/null && { echo "PORT $p BUSY"; exit 3; }; done
mkdir -p $W/res/cors
modeargs=(--env prod --backend-only --backend-port $BP)
[ "${MODE:-prod}" = dev ] && modeargs=(--backend-only --backend-port $BP)
( export NA_TX=fastapi "$@"; $W/bin/srv.sh start cors_$label $venv netapp "${modeargs[@]}" >/dev/null )
( cd $SB && setsid python3 -I -m http.server $FP -d ${STATIC:-$W/static/$venv/site} > $W/logs/static_$label.log 2>&1 & echo $! > $W/logs/static_$label.pid )
LABEL=cors_$label $W/bin/srv.sh wait http://localhost:$BP/ping 240 >/dev/null || { echo "backend not up"; }
$W/bin/srv.sh wait http://localhost:$FP/ 30 >/dev/null
echo "##### $label ($venv, ${MODE:-prod}) env: $*"
(cd $SB && $NP $DPY $W/drivers/cors_probe.py http://localhost:$BP $W/res/cors/$label.probe.json \
  http://localhost:$FP http://evil.example null http://localhost:$FP/ http://LOCALHOST:$FP http://localhost:$((FP+1)) http://127.0.0.1:$FP)
if [ "${BROWSER:-1}" = 1 ]; then
  (cd $SB && $NP timeout 300 $DPY $W/drivers/drv.py http://localhost:$FP basic $W/res/cors/$label.basic.json --shots $W/res/cors/shots_$label > $W/res/cors/$label.basic.txt; head -16 $W/res/cors/$label.basic.txt)
fi
kill $(lsof -t -iTCP:$FP -sTCP:LISTEN) 2>/dev/null
$W/bin/srv.sh stop cors_$label >/dev/null
grep -i -E "cors|origin|not an accepted|403|400 " $W/logs/cors_$label.log | grep -v NA_MARK | cut -c1-200 | sort | uniq -c | head -8 | sed 's/^/  server log: /'
