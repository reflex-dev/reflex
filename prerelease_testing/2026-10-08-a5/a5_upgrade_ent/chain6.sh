#!/usr/bin/env bash
# reflex-azure-auth rerun with the fixed driver (event pumping), after chain3b: a5 dev+prod, a4 dev+prod.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent; T=$W/tp/az
until [ -f $W/chain3b.done ]; do sleep 5; done
mkdir -p $T/logs/attempt1; mv $T/logs/run-az-a5.txt $T/logs/run-az-a4.txt $T/logs/a5-*-az.json $T/logs/a4-*-az.json $T/logs/az-a5-*.server.log $T/logs/az-a4-*.server.log $T/logs/attempt1/ 2>/dev/null
$T/bin/run_az.sh a5_upgrade_ent-az a5 dev,prod > $T/logs/run-az-a5.txt 2>&1
$T/bin/run_az.sh a5_upgrade_ent-az4 a4 dev,prod > $T/logs/run-az-a4.txt 2>&1
echo CHAIN6_DONE $(date +%T) > $W/chain6.done
