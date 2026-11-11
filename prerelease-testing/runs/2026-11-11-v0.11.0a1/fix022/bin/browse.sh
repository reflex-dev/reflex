#!/usr/bin/env bash
# browse.sh <label> <url> : drive Chromium (count must reach 2)
SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022
D=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/envs/driver/bin/python
(cd $SB && NO_PROXY=localhost,127.0.0.1,.test no_proxy=localhost,127.0.0.1,.test timeout 120 $D $SB/bin/drv.py "$2" $SB/res/$1.json $SB/res/$1.png 2>&1 | head -3 | sed "s/^/  [$1] /")
