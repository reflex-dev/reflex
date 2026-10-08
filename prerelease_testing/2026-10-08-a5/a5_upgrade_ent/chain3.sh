#!/usr/bin/env bash
# Extras after chain 2: expiry / proactive-refresh flows on a5 (entauth, dev Redis) and the deeplink probe on 0.9.12 + enterprise a5.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent; E=$W/ent/auth
until [ -f $W/chain2.done ]; do sleep 5; done
$E/bin/seq_deeplink.sh s912-ent-a5 s912e5 > $E/logs/seq-deeplink-s912e5.txt 2>&1
$E/bin/infra.sh start > $E/logs/expiry-infra.txt 2>&1
$E/scripts/expiry_matrix.sh a5-ent entauth_a5e a5e proactive expire_norefresh expire_closed_tab revoke > $E/logs/expiry-matrix-a5e.txt 2>&1
$E/bin/infra.sh stop >> $E/logs/expiry-infra.txt 2>&1
echo CHAIN3_DONE $(date +%T) > $W/chain3.done
