#!/usr/bin/env bash
# Part 2/3 chain after chain 1: N-001 prod CRUD, in-place upgrades (fd, twr, twa4, gh), third-party flows on a5.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent
until [ -f $W/ent/chain1.done ]; do sleep 5; done
$W/inst/bin/prod_crud.sh > $W/inst/logs/prod_crud.txt 2>&1
$W/up/bin/seq_fd.sh > $W/up/logs/seq-fd.txt 2>&1
$W/up/bin/seq_twr.sh > $W/up/logs/seq-twr.txt 2>&1
$W/up/bin/seq_twa4.sh > $W/up/logs/seq-twa4.txt 2>&1
$W/up/bin/seq_gh.sh > $W/up/logs/seq-gh.txt 2>&1
$W/tp/bin/seq_tp.sh a5_upgrade_ent-tp a5 > $W/tp/logs/seq-tp-a5.txt 2>&1
$W/tp/bin/run_google.sh a5_upgrade_ent-tp a5 > $W/tp/logs/run-google-a5.txt 2>&1
echo CHAIN2_DONE $(date +%T) > $W/chain2.done
