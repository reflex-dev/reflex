#!/usr/bin/env bash
# Wait for seq_fd.sh to finish, then run github-stats, twitter prod+Redis (0.9.12 -> a4), twitter prod+Redis (a3 -> a4), one at a time.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/up
until grep -q "### fd done" $W/logs/seq-fd.txt || ! pgrep -f "bin/seq_fd.sh" >/dev/null; do sleep 5; done
$W/bin/seq_gh.sh > $W/logs/seq-gh.txt 2>&1
$W/bin/seq_twr.sh > $W/logs/seq-twr.txt 2>&1
$W/bin/seq_twa3.sh > $W/logs/seq-twa3.txt 2>&1
$W/bin/ports.sh > $W/logs/ports-after-chain.txt
echo CHAIN_DONE >> $W/logs/seq-twa3.txt
