#!/usr/bin/env bash
# Replaces chain3/4/5 (re-ordered to save time): after chain 2 -> expiry / proactive refresh on a5, reflex-azure-auth on a5
# (a4 only if a5 differs), final-driver deeplink rerun on a5, then deeplink on 0.9.12 + enterprise a5.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent; E=$W/ent/auth; T=$W/tp/az
until [ -f $W/chain2.done ]; do sleep 5; done
$E/bin/infra.sh start > $E/logs/expiry-infra.txt 2>&1
$E/scripts/expiry_matrix.sh a5-ent entauth_a5e a5e proactive expire_norefresh expire_closed_tab revoke > $E/logs/expiry-matrix-a5e.txt 2>&1
$E/bin/infra.sh stop >> $E/logs/expiry-infra.txt 2>&1
$T/bin/run_az.sh a5_upgrade_ent-az a5 dev,prod > $T/logs/run-az-a5.txt 2>&1
grep -q "SUMMARY a5-dev A True B True C True errors 0" $T/logs/run-az-a5.txt && grep -q "SUMMARY a5-prod A True B True C True" $T/logs/run-az-a5.txt || $T/bin/run_az.sh a5_upgrade_ent-az4 a4 dev,prod > $T/logs/run-az-a4.txt 2>&1
mkdir -p $E/logs/attempt2; mv $E/logs/a5e-dl-* $E/logs/seq-deeplink-a5e.txt $E/logs/attempt2/ 2>/dev/null
$E/bin/seq_deeplink.sh a5-ent a5e > $E/logs/seq-deeplink-a5e.txt 2>&1
$E/bin/seq_deeplink.sh s912-ent-a5 s912e5 dev > $E/logs/seq-deeplink-s912e5.txt 2>&1
echo CHAIN3B_DONE $(date +%T) > $W/chain3b.done
