#!/bin/bash
# drive.sh <actions.json> <tag>
W=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/final
cd $W/drv && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 UV_CACHE_DIR=$W/uvcache-drv uv --no-config run -q --script /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py "${3:-http://localhost:3500/}" --settle 2500 --actions "$(sed "s#SHOT#$W/shots/$2.png#" $1)" --report $W/logs/$2.drive.json 2>&1 | grep -v UV_NATIVE | tee $W/logs/$2.drive.txt
exit ${PIPESTATUS[0]}
