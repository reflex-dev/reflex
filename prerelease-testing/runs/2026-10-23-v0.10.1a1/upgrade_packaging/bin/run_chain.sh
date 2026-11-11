#!/usr/bin/env bash
# In-place upgrade chain (one app server set at a time), ports inside 3460-3499 / 8460-8499:
#   twitter prod+Redis (+rollback) P=3498 RP=8499 -> github-stats 3492/8492 (+stub 8498) -> upload 3486/8486 -> nba 3486/8486
# then the blank-app smoke (init + dev + prod) on new, n001-pip311, n001-uv315 at 3488/8488.
set -u
: "${SB:?}"; : "${W:?}"
export NEW=new PREV=prev VENV_PREFIX=upgrade_packaging UP_EXTRA='pydantic<2.15'
cd "$SB"
L=$W/up/logs
echo "### chain start $(date +%T)"
P=3498 RP=8499 bash "$W/up/bin/seq_twr.sh" > "$L/seq_twr.out" 2>&1; echo "twr rc=$? $(date +%T)"
FP=3492 BP=8492 STUBP=8498 bash "$W/up/bin/seq_gh.sh" > "$L/seq_gh.out" 2>&1; echo "gh rc=$? $(date +%T)"
FP=3486 BP=8486 bash "$W/up/bin/seq_app.sh" upload > "$L/seq_upload.out" 2>&1; echo "upload rc=$? $(date +%T)"
FP=3486 BP=8486 bash "$W/up/bin/seq_app.sh" nba > "$L/seq_nba.out" 2>&1; echo "nba rc=$? $(date +%T)"
FP=3488 BP=8488 bash "$W/smoke/bin/seq_smoke.sh" new upgrade_packaging-n001-pip311 upgrade_packaging-n001-uv315 > "$W/smoke/seq_smoke.out" 2>&1; echo "smoke rc=$? $(date +%T)"
bash "$W/bin/ports.sh" $(seq 3460 3499) $(seq 8460 8499)
echo "### chain done $(date +%T)"
