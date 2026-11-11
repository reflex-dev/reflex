#!/usr/bin/env bash
# The documented split deployment (docs/hosting/self-hosting.md @ v0.11.0a1), on our ports:
#   reflex run --env prod --backend-only --backend-port 8348
#   REFLEX_API_URL=http://localhost:8348 reflex run --env prod --frontend-only --frontend-port 3348
# then Chromium on http://localhost:3348 (connect scenario).   split_doc.sh <venv> <label> [backend ENV=VAL ...]
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1 label=$2; shift 2
FP=${FP:-3348} BP=${BP:-8348}
for p in $FP $BP; do curl --noproxy '*' -s -m 1 localhost:$p >/dev/null && { echo "PORT $p BUSY"; exit 3; }; done
( [ $# -gt 0 ] && export "$@"; $W/bin/srv.sh start split_be_$label $venv netapp --env prod --backend-only --backend-port $BP >/dev/null )
LABEL=split_be_$label $W/bin/srv.sh wait http://localhost:$BP/ping 240
( export REFLEX_API_URL=http://localhost:$BP; $W/bin/srv.sh start split_fe_$label $venv netapp --env prod --frontend-only --frontend-port $FP >/dev/null )
LABEL=split_fe_$label $W/bin/srv.sh wait http://localhost:$FP/ 400
echo "##### split_doc $label ($venv) backend env: $*"
(cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 200 $SB/envs/driver/bin/python $W/drivers/drv.py http://localhost:$FP connect $W/res/split_$label.json --shots $W/res/shots/split_$label | head -8)
$W/bin/srv.sh stop split_fe_$label >/dev/null; $W/bin/srv.sh stop split_be_$label >/dev/null
grep -h -i "accepted origin" $W/logs/split_be_$label.log | head -3 | sed 's/^/  backend log: /'
