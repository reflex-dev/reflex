#!/usr/bin/env bash
# reflex-azure-auth on a5 (dev + prod) and a4 (dev) after chain 3.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent; T=$W/tp/az
until [ -f $W/chain3.done ]; do sleep 5; done
$T/bin/run_az.sh a5_upgrade_ent-az a5 dev,prod > $T/logs/run-az-a5.txt 2>&1
$T/bin/run_az.sh a5_upgrade_ent-az4 a4 dev,prod > $T/logs/run-az-a4.txt 2>&1
echo CHAIN4_DONE $(date +%T) > $W/chain4.done
