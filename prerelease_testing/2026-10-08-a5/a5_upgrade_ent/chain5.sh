#!/usr/bin/env bash
# Final-driver rerun of the deeplink probe on a5 (dev + prod) after chain 4, so a5 and a4 ran the identical driver.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent; E=$W/ent/auth
until [ -f $W/chain4.done ]; do sleep 5; done
mkdir -p $E/logs/attempt2; mv $E/logs/a5e-dl-* $E/logs/seq-deeplink-a5e.txt $E/logs/attempt2/ 2>/dev/null
$E/bin/seq_deeplink.sh a5-ent a5e > $E/logs/seq-deeplink-a5e.txt 2>&1
echo CHAIN5_DONE $(date +%T) > $W/chain5.done
