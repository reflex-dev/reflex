#!/usr/bin/env bash
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_upgrade
until grep -q "^### twr done\|BASE DRIVE LEFT NO TOKEN" $W/logs/seq-twr.txt 2>/dev/null; do sleep 5; done; sleep 3
$W/bin/seq_guide2.sh > $W/logs/seq-guide3.txt 2>&1
