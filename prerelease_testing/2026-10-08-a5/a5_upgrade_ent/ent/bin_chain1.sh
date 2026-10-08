#!/usr/bin/env bash
# Part 1 chain (one app server at a time): waits for seq_ent_auth a5e, then N-032 prod a5, deeplink a5, the a4 baseline
# (seq_ent_auth + N-032 prod + deeplink on a4-ent), then the grid/demo smoke on a5.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; EN=$SB/apps/a5_upgrade_ent/ent; E=$EN/auth
while pgrep -f "bin/seq_ent_auth.sh a5-ent" > /dev/null; do sleep 5; done
$E/bin/seq_n032_prod.sh a5-ent a5e > $E/logs/seq-n032-prod-a5e.txt 2>&1
$E/bin/seq_deeplink.sh a5-ent a5e > $E/logs/seq-deeplink-a5e.txt 2>&1
$E/bin/seq_deeplink.sh a4-ent a4e > $E/logs/seq-deeplink-a4e.txt 2>&1
$E/bin/seq_ent_auth.sh a4-ent a4e 123 > $E/logs/seq-ent-auth-a4e.txt 2>&1
$E/bin/seq_n032_prod.sh a4-ent a4e > $E/logs/seq-n032-prod-a4e.txt 2>&1
$EN/grid/bin/seq_grid.sh a5-ent a5 12 > $EN/grid/logs/seq-grid-a5.txt 2>&1
echo CHAIN1_DONE $(date +%T) > $EN/chain1.done
